"""Emit the shipped ``verify_in_maya.py`` parity scripts.

Per node family (geometry / deformer / IK solver / scalar) this builds the
Maya-side equivalence check that compares the compiled native node against the
original mPyNode. Built by plain string concatenation (no % / .format /
f-string) because the generated bodies themselves contain ``%`` and ``{}``.
"""

from __future__ import annotations

import json

from mpynode.native import compiler as codegen
from mpynode.native.toolchain import toolchain


# Every input the deformer / IK / scalar scripts pick is fitted inside the
# attr's declared range before it is set. setAttr refuses a value past a hard
# min or max (the generic verify stopped on Mesh Maze's solutionLength, max 1),
# and a soft range, where present, is the span the attr is meant for.
# attributeQuery reports both in the UI units setAttr reads, so a unit type
# (doubleAngle, doubleLinear) needs no conversion here. The same text goes into
# each script so it stays standalone; the harness twin is
# native.toolchain.verify._drive_fitter.
_FIT_HELPERS = r'''# Every pick lands inside its attr's range: see _fit.
_RANGED = ("double", "float", "long", "short", "doubleAngle", "doubleLinear")
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
        r = (v - lo) % (2 * span)
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


'''


def _verify_script(spec: dict) -> str:
    """A Maya-side equivalence check: compiled node vs original mPyNode.

    Dispatches to a geometry-based check for the deformer family, else the
    scalar plug check. Built by plain concatenation (no % / .format / f-string)
    because the generated body itself contains '%' and '{}'.
    """
    base = spec.get("suggested", {}).get("mpx_base", "MPxNode")
    if codegen._geo_kind(spec):
        return _verify_script_geo(spec)
    if base in codegen._DEFORMER_BASES:
        return _verify_script_deformer(spec)
    if base == codegen._IKSOLVER_BASE:
        return _verify_script_iksolver(spec)
    return _verify_script_scalar(spec)


def _verify_script_geo(spec: dict) -> str:
    """Honest geometry parity artifact. Rather than re-implement (and drift
    from) the parity logic, the shipped script embeds the spec and runs the
    AUTHORITATIVE geo branch, verify._verify_one -- which rebuilds
    the Python original, drives identical inputs, and compares topology + every
    point off the geo output plug. Prints PASS/FAIL/SKIP so it reads like the
    other verify artifacts."""
    name = spec["suggested"]["node_type_name"]
    consts = (
        '"""Equivalence check: compiled native GEOMETRY node vs the original mPyNode.\n'
        "Run in Maya. Rebuilds the Python original from the embedded spec, builds\n"
        "the compiled node, drives identical inputs, and compares the built\n"
        "geometry (topology + every point) via the authoritative geo parity\n"
        "branch in verify._verify_one.\n"
        '"""\n'
        "import os, json\n"
        "import maya.cmds as cmds\n\n"
        "BUNDLE = os.path.join(os.path.dirname(__file__), "
        + repr(name + toolchain.plugin_ext()) + ")\n"
        "SPEC = json.loads(" + repr(json.dumps(spec)) + ")\n\n\n"
    )
    body = r'''def run():
    from mpynode.native.toolchain import verify as _cc
    if not cmds.pluginInfo(os.path.basename(BUNDLE), q=True, loaded=True):
        cmds.loadPlugin(BUNDLE)
    row = _cc._verify_one(cmds, BUNDLE, SPEC)
    print("GEO VERIFY", row)
    if not row.get("ran"):
        print("VERIFY SKIP (" + str(row.get("reason")) + ")")
        return True
    if row.get("pass"):
        print("VERIFY PASS maxerr", row.get("maxerr"))
        return True
    print("VERIFY FAIL", row.get("reason"), row.get("maxerr"))
    return False


if __name__ == "__main__":
    run()
'''
    return consts + body


def _verify_script_deformer(spec: dict) -> str:
    """Mesh-based equivalence: applies the original mPy deformer and the
    compiled deformer to two identical spheres and compares deformed points.
    """
    name        = spec["suggested"]["node_type_name"]
    src_type    = spec.get("mpy_type") or "mPyDeformer"
    is_skin     = spec.get("suggested", {}).get("mpx_base") == "MPxSkinCluster"
    user_inputs = {n: m["type"] for n, m in (spec.get("inputs") or {}).items()}

    consts = (
        '"""Equivalence check: compiled native DEFORMER vs the original mPy deformer.\n'
        "Run in Maya. Builds two identical spheres, applies the original mPy\n"
        "deformer (expression copied from the source) to one and the compiled\n"
        "deformer to the other, then compares object-space points over random\n"
        "envelope/input samples.\n"
        '"""\n'
        "import os, math, random\n"
        "import maya.cmds as cmds\n\n"
        'BUNDLE = os.path.join(os.path.dirname(__file__), ' + repr(name + toolchain.plugin_ext()) + ")\n"
        "NODE_TYPE = " + repr(name) + "\n"
        "SRC_TYPE = " + repr(src_type) + "\n"
        "COMPUTE = " + repr(spec.get("compute") or "") + "\n"
        "INIT = " + repr(spec.get("init") or "") + "\n"
        "USER_INPUTS = " + json.dumps(user_inputs) + "\n"
        "IS_SKIN = " + ("True" if is_skin else "False") + "\n"
        "TOL = 1e-3\n\n\n"
    )
    body = r'''def _sample(t):
    if t == "bool": return random.choice([0, 1])
    if t == "long": return random.randint(-3, 3)
    if t == "enum": return random.randint(0, 1)
    if t in ("double3", "euler", "position"):
        return [random.uniform(-2, 2) for _ in range(3)]
    return random.uniform(-2, 2)


def _set(node, attr, t, v):
    if t in ("double3", "euler", "position"):
        cmds.setAttr(node + "." + attr, v[0], v[1], v[2], type="double3")
    else:
        cmds.setAttr(node + "." + attr, v)


def _pts(mesh):
    return cmds.xform(mesh + ".vtx[*]", q=True, os=True, t=True)


def _apply(deformer_type, configure):
    tr = cmds.polySphere(r=1, sx=12, sy=12, ch=False)[0]
    d = cmds.deformer(tr, type=deformer_type)[0]
    if configure:
        configure(d)
    return tr, d


def run(samples=12):
    if not cmds.pluginInfo(os.path.basename(BUNDLE), q=True, loaded=True):
        cmds.loadPlugin(BUNDLE)
    if IS_SKIN:
        print("NOTE: skinCluster parity needs a bound influence set "
              "(matrix[]/bindPreMatrix[]/weights). Without joints both nodes "
              "are identity; wire a rig for a meaningful comparison.")

    import mpynode

    def cfg(node):
        w = mpynode.wrap_node(node)
        for nm, t in USER_INPUTS.items():
            try:
                w.add_input_attr(nm, t)
            except Exception:
                pass
        if INIT.strip():
            w.set_init_expression(INIT)
        w.set_compute_expression(COMPUTE)

    src_tr, src_d = _apply(SRC_TYPE, cfg)
    cmp_tr, cmp_d = _apply(NODE_TYPE, None)

    fails = 0
    for _ in range(samples):
        env = random.uniform(0.0, 1.0)
        cmds.setAttr(src_d + ".envelope", env)
        cmds.setAttr(cmp_d + ".envelope", env)
        for a, t in USER_INPUTS.items():
            v = _fit((src_d, cmp_d), a, t, _sample(t))
            if cmds.objExists(src_d + "." + a):
                _set(src_d, a, t, v)
            if cmds.objExists(cmp_d + "." + a):
                _set(cmp_d, a, t, v)
        a_pts = _pts(src_tr)
        b_pts = _pts(cmp_tr)
        if len(a_pts) != len(b_pts):
            print("VERTEX COUNT MISMATCH", len(a_pts), len(b_pts))
            fails += 1
            continue
        for i in range(len(a_pts)):
            if abs(a_pts[i] - b_pts[i]) > TOL:
                print("MISMATCH coord", i, a_pts[i], "!=", b_pts[i])
                fails += 1
                break
    print("VERIFY", "PASS" if not fails else ("FAIL " + str(fails)))
    return fails == 0


if __name__ == "__main__":
    run()
'''
    return consts + _FIT_HELPERS + body


def _verify_script_iksolver(spec: dict) -> str:
    """IK parity: build two identical joint chains, drive one with the original
    Python mPyIkSolver and one with the compiled solver, move the handle to a
    series of goals (sampling scalar inputs too), and compare JOINT WORLD
    POSITIONS (robust to euler representation). Mesh inputs need a wired floor --
    see the example's dedicated harness; here a connected mesh is skipped.
    """
    name     = spec["suggested"]["node_type_name"]
    src_type = spec.get("mpy_type") or "mPyIkSolver"
    scalar_inputs = {n: m["type"] for n, m in (spec.get("inputs") or {}).items()
                     if m.get("type") in ("float", "double", "long", "bool", "enum")}
    enum_fields = {n: (m.get("enum_names") or [])
                   for n, m in (spec.get("inputs") or {}).items()
                   if m.get("type") == "enum"}
    mesh_inputs = [n for n, m in (spec.get("inputs") or {}).items()
                   if m.get("type") == "mesh"]

    consts = (
        '"""IK equivalence check: compiled native solver vs original mPyIkSolver.\n'
        "Builds two 3-joint chains, drives one with each solver, moves the handle\n"
        "to several goals, and compares joint world positions.\n"
        '"""\n'
        "import os, math, random\n"
        "import maya.cmds as cmds\n\n"
        'BUNDLE = os.path.join(os.path.dirname(__file__), ' + repr(name + toolchain.plugin_ext()) + ")\n"
        "NODE_TYPE = " + repr(name) + "\n"
        "SRC_TYPE = " + repr(src_type) + "\n"
        "COMPUTE = " + repr(spec.get("compute") or "") + "\n"
        "INIT = " + repr(spec.get("init") or "") + "\n"
        "SCALAR_INPUTS = " + json.dumps(scalar_inputs) + "\n"
        "ENUM_FIELDS = " + json.dumps(enum_fields) + "\n"
        "MESH_INPUTS = " + json.dumps(mesh_inputs) + "\n"
        "TOL = 1e-3\n\n\n"
    )
    body = r'''def _chain(prefix, n=3, blen=5.0):
    cmds.select(clear=True)
    js = []
    for i in range(n):
        j = cmds.joint(p=(i * blen, 0, 0), name=prefix + "_j%d" % i)
        js.append(j)
    # slight bend so the plane is well-defined
    cmds.setAttr(js[1] + ".preferredAngleZ", 10.0)
    return js


def _solver_inst(node_type, configure=None):
    inst = cmds.createNode(node_type)
    if configure:
        configure(inst)
    return inst


def _sample(t, fields):
    if t == "bool":
        return random.choice([0, 1])
    if t == "long":
        return random.randint(-3, 3)
    if t == "enum":
        return random.randint(0, max(0, len(fields) - 1))
    return random.uniform(0.1, 2.0)


def _set(node, attr, v):
    if cmds.objExists(node + "." + attr):
        try:
            cmds.setAttr(node + "." + attr, v)
        except Exception:
            pass


def _ws(joints):
    out = []
    for j in joints:
        p = cmds.xform(j, q=True, ws=True, t=True)
        out.extend(p)
    return out


def run(samples=8):
    if not cmds.pluginInfo(os.path.basename(BUNDLE), q=True, loaded=True):
        cmds.loadPlugin(BUNDLE)
    import mpynode

    def cfg(node):
        w = mpynode.wrap_node(node)
        for nm, t in SCALAR_INPUTS.items():
            try:
                w.add_input_attr(nm, t)
            except Exception:
                pass
        for nm in MESH_INPUTS:
            try:
                w.add_input_attr(nm, "mesh")
            except Exception:
                pass
        if INIT.strip():
            w.set_init_expression(INIT)
        w.set_compute_expression(COMPUTE)

    src_solver = _solver_inst(SRC_TYPE, cfg)
    cmp_solver = _solver_inst(NODE_TYPE, None)

    src_js = _chain("src")
    src_h = cmds.ikHandle(sj=src_js[0], ee=src_js[-1], sol=src_solver)[0]
    cmp_js = _chain("cmp")
    cmp_h = cmds.ikHandle(sj=cmp_js[0], ee=cmp_js[-1], sol=cmp_solver)[0]

    if MESH_INPUTS:
        print("NOTE: mesh input(s)", MESH_INPUTS, "not wired in this generic "
              "check; use the example's dedicated harness for floor parity.")

    fails = 0
    maxerr = 0.0
    for _ in range(samples):
        goal = (random.uniform(2, 9), random.uniform(-4, 4), random.uniform(-4, 4))
        for h in (src_h, cmp_h):
            cmds.xform(h, ws=True, t=goal)
        for a, t in SCALAR_INPUTS.items():
            v = _fit((src_solver, cmp_solver), a, t,
                     _sample(t, ENUM_FIELDS.get(a, [])))
            _set(src_solver, a, v)
            _set(cmp_solver, a, v)
        cmds.refresh(force=True)
        a_ws, b_ws = _ws(src_js), _ws(cmp_js)
        for i in range(min(len(a_ws), len(b_ws))):
            e = abs(a_ws[i] - b_ws[i])
            if e > maxerr:
                maxerr = e
            if e > TOL:
                fails += 1
    print("IK maxerr", maxerr)
    print("VERIFY", "PASS" if not fails else ("FAIL " + str(fails)))
    return fails == 0


if __name__ == "__main__":
    run()
'''
    return consts + _FIT_HELPERS + body


def _verify_script_scalar(spec: dict) -> str:
    name    = spec["suggested"]["node_type_name"]
    inputs  = {n: m["type"] for n, m in (spec.get("inputs") or {}).items()}
    outputs = {n: m["type"] for n, m in (spec.get("outputs") or {}).items()}

    consts = (
        '"""Equivalence check: compiled native node vs the original mPyNode.\n'
        "Run in Maya. Loads the .bundle, samples inputs, compares outputs.\n"
        '"""\n'
        "import os, math, random\n"
        "import maya.cmds as cmds\n\n"
        'BUNDLE = os.path.join(os.path.dirname(__file__), ' + repr(name + toolchain.plugin_ext()) + ")\n"
        "NODE_TYPE = " + repr(name) + "\n"
        "SOURCE = " + repr(spec.get("source_node")) + "\n"
        "INPUTS = " + json.dumps(inputs) + "\n"
        "OUTPUTS = " + json.dumps(outputs) + "\n"
        "TOL = 1e-4\n\n\n"
    )
    body = r'''def _sample(t):
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
'''
    return consts + _FIT_HELPERS + body
