"""IK equivalence check: compiled native solver vs original mPyIkSolver.
Builds two 3-joint chains, drives one with each solver, moves the handle
to several goals, and compares joint world positions.
"""
import os, math, random
import maya.cmds as cmds

BUNDLE = os.path.join(os.path.dirname(__file__), 'twoBoneIK.bundle')
NODE_TYPE = 'twoBoneIK'
SRC_TYPE = 'mPyIkSolver'
COMPUTE = '# 2-bone analytic IK (law of cosines) producing per-joint WORLD matrices.\n# Runs during the IK solve when this node is the solver on an ikHandle driving a\n# 3-joint chain (root -> mid -> tip). The solve is jointOrient-agnostic: it reads\n# each joint\'s rest (bind) world frame and rotates it so the bone aims correctly,\n# then the bridge applies the result via offsetParentMatrix (rotate-only by\n# default) -- the joints\' own channels and jointOrient are left untouched.\n#\n# NOTE: this minimal solver\'s bend plane comes from the pole vector if present,\n# else the rest knee direction (stable, avoids knee-pop). Add a dedicated pole\n# input + reference axis for production rigs.\nimport math\nimport numpy as np\n\njoints = self.joints\nif len(joints) >= 3:\n    p0 = np.asarray(joints[0]["world_position"], float)   # root (hip)\n    p1 = np.asarray(joints[1]["world_position"], float)   # mid  (knee)\n    p2 = np.asarray(joints[2]["world_position"], float)   # tip  (ankle)\n    W0 = np.asarray(joints[0]["world_matrix"], float).reshape(4, 4)\n    W1 = np.asarray(joints[1]["world_matrix"], float).reshape(4, 4)\n    B1 = float(np.linalg.norm(p1 - p0))       # upper bone length (rigid)\n    B2 = float(np.linalg.norm(p2 - p1))       # lower bone length (rigid)\n\n    target = np.asarray(self.end_effector, float)\n    goal_vec = target - p0\n    reach = float(np.linalg.norm(goal_vec))\n    if reach > 1e-9 and B1 > 1e-9 and B2 > 1e-9:\n        goal_dir = goal_vec / reach\n        # clamp reachable distance (law-of-cosines domain)\n        d = min(max(reach, abs(B1 - B2) + 1e-4), B1 + B2 - 1e-4)\n        goal_pt = p0 + d * goal_dir\n\n        pole = np.asarray(self.pole_vector, float)\n        ref = (pole - p0) if float(np.linalg.norm(pole)) > 1e-6 else (p1 - p0)\n        bend_n = np.cross(goal_dir, ref)\n        if float(np.linalg.norm(bend_n)) < 1e-6:\n            bend_n = np.cross(goal_dir, np.array([0.0, 0.0, 1.0]))\n        if float(np.linalg.norm(bend_n)) < 1e-6:\n            bend_n = np.cross(goal_dir, np.array([1.0, 0.0, 0.0]))\n        bend_n = bend_n / np.linalg.norm(bend_n)\n\n        cos_a = (B1 * B1 + d * d - B2 * B2) / (2.0 * B1 * d)\n        alpha = math.acos(max(-1.0, min(1.0, cos_a)))\n\n        def rot3(axis, ang):\n            # column-vector Rodrigues rotation (R @ v) about a unit axis.\n            x, y, z = axis[0], axis[1], axis[2]\n            c = math.cos(ang)\n            s = math.sin(ang)\n            k = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])\n            return np.eye(3) + s * k + (1.0 - c) * (k @ k)\n\n        upper_dir = rot3(bend_n, alpha) @ goal_dir\n        upper_dir = upper_dir / np.linalg.norm(upper_dir)\n        knee_pt = p0 + B1 * upper_dir\n        lower_dir = goal_pt - knee_pt\n        lower_dir = lower_dir / np.linalg.norm(lower_dir)\n\n        def aim(w_rest, rest_dir, new_dir):\n            # World matrix that re-aims a joint\'s bind frame so its bone points\n            # from rest_dir to new_dir. Returns w_rest @ delta, where delta\'s\n            # rotation is the transpose of the (column) rotation mapping\n            # rest_dir->new_dir (row-vector Maya). Only rotation is used\n            # downstream (translate is gated off), so the delta translation is 0.\n            a = rest_dir / np.linalg.norm(rest_dir)\n            b = new_dir / np.linalg.norm(new_dir)\n            v = np.cross(a, b)\n            s = float(np.linalg.norm(v))\n            c = float(np.dot(a, b))\n            if s < 1e-9:\n                rct = np.eye(3)\n            else:\n                rct = rot3(v / s, -math.acos(max(-1.0, min(1.0, c))))\n            delta = np.eye(4)\n            delta[:3, :3] = rct\n            return w_rest @ delta\n\n        self.world_matrices[0] = aim(W0, p1 - p0, upper_dir)   # root aims upper bone\n        self.world_matrices[1] = aim(W1, p2 - p1, lower_dir)   # mid  aims lower bone\n        # tip (joint 2) is left as None -> it follows the chain.\n        self.apply_rotate = True       # reorient the joints...\n        self.apply_translate = False   # ...keep their rest translate (bone lengths)\n        self.apply_scale = False\n'
INIT = 'import math\nimport numpy as np\n'
SCALAR_INPUTS = {}
ENUM_FIELDS = {}
MESH_INPUTS = []
TOL = 1e-3


def _chain(prefix, n=3, blen=5.0):
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
    if t == "int":
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
            v = _sample(t, ENUM_FIELDS.get(a, []))
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
