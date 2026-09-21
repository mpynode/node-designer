"""Equivalence check: compiled native DEFORMER vs the original mPy deformer.
Run in Maya. Builds two identical spheres, applies the original mPy
deformer (expression copied from the source) to one and the compiled
deformer to the other, then compares object-space points over random
envelope/input samples.
"""
import os, random
import maya.cmds as cmds

BUNDLE      = os.path.join(os.path.dirname(__file__), 'comboCorrectives.mll')
NODE_TYPE   = 'comboCorrectives'
SRC_TYPE    = 'mPyBlendShape'
COMPUTE     = "# Corrective blendShape: in-betweens and combos, resolved from tables.\n#\n# The naming convention lives in the ALIASES, and it is decoded ONCE, in Python,\n# by MPyBlendShape.rebuild() -- never here:\n#\n#     browUp                a main target, driven by its own weight\n#     browUp50              an IN-BETWEEN of browUp, peaking at 0.50\n#     browUp_mouthOpen      a COMBO, active when both drivers are up\n#\n# Names cannot be read in a compute at all. Alias lookup is a side-channel DG\n# query, and those return EMPTY on the Evaluation-Manager worker thread that\n# deform() runs on -- so it would be unreliable interpreted and impossible\n# compiled. What crosses into the compute is pure number:\n#\n#     interBase[t]    the main target an in-between corrects, else -1\n#     interKnot[t]    where it peaks (0.5 for browUp50)\n#     comboOffset[t] .. comboOffset[t+1]   slice of comboDriver for target t\n#     comboDriver[j]  a driver target index\n#\n# Every target stores its RAW `sculpt - base` offsets. A corrective is sculpted\n# as the correction ITSELF -- what to add once its drivers are already posed --\n# so there is nothing to subtract at bake time. That is also why dialling one by\n# hand shows exactly the shape it was sculpted as.\n#\n# The rules live in the INIT tab as three ordinary functions --\n# `inbetween_hat`, `combo_blend`, `resolve_morph_weights` -- so the\n# maths is right there to read and change. There is no shared weight resolver\n# behind them: whatever maths a rig wants lives in ITS Init and Compute, in\n# the open. Init transpiles with the Compute, so an edited rule compiles too.\n#\n# Correctives are ADDITIVE here: a corrective keeps whatever is keyed on its own\n# channel and the driven amount is added on top. `applyCorrectives` and\n# `applyCombos` switch the driven half off without unhooking anything, so you can\n# key the drivers and watch each contribution on its own.\n\n# Construction history is automatic: `self.morphs.deltas` reads a target's\n# offsets straight off its CONNECTED mesh, so sculpting one reaches the deform\n# as you drag. A target with no connection falls back to its baked deltas, which\n# is what makes deleting a target leave the shape driving. Switch `liveTargets`\n# off to pin the deform to the baked tables. Compiled nodes follow their targets\n# too -- they read every CONNECTED one, where interpreted skips the slots that\n# resolve to zero weight, so the result matches and only the cost differs.\n\nmesh = self.outputGeometry[0]\nbase = mesh.getPoints()\n\nw = resolve_morph_weights(self.weight, self.interBase, self.interKnot,\n                          self.comboOffset, self.comboDriver,\n                          self.applyCorrectives, self.applyCombos)\n\nmesh.setPoints(base + self.envelope * self.morphs.deltas(base, w))\n"
INIT        = '# The corrective maths, as three plain functions. Init runs ONCE per file\n# lifecycle and its globals are visible to the Compute, so this is where the\n# rules live -- edit them here and the Compute stays a four-line summary.\n#\n# These transpile exactly like the Compute does: a function defined in Init is\n# handed to the C++ helper parser, so the compiled node calls the SAME rules,\n# not a second implementation. Keep them in the loop dialect (`for i in\n# range(...)`, integer indexing, explicit float()/int() on ARRAY reads) and they\n# lower whole. Note the casts on `raw[t]` / `cdrv[j]` are NOT defensive noise --\n# the transpiler needs them to type the C++; dropping them drops the node to the\n# AI porter. A `self.<attr>` read is already the right Python type and must NOT\n# be recast.\nimport numpy as np\n\n\ndef inbetween_hat(driver, knot, ibase, iknot, main):\n    """The in-between rule: a CROSS-BLENDING hat on the MAIN target\'s weight.\n\n    1.0 when the driver sits exactly on this knot, falling to 0 at the ADJACENT\n    knots on the same main -- not at the ends of the driver\'s travel. So with\n    jawDrop25/50/75 on one driver, jawDrop75 blends 0.5 (0.) -> 0.75 (1.) ->\n    1.0 (0.) and the three hand off to each other instead of all firing at once.\n    A lone in-between still spans 0 -> knot -> 1, because there is no neighbour\n    to hand off to. Want a softer shoulder? Return a smoothstep of this.\n    """\n    lo = 0.0\n    hi = 1.0\n    for j in range(ibase.shape[0]):\n        if int(ibase[j]) == main:\n            k = float(iknot[j])\n            if k < knot and k > lo:\n                lo = k\n            if k > knot and k < hi:\n                hi = k\n    h = 0.0\n    if driver > lo:\n        if driver <= knot:\n            if knot > lo:\n                h = (driver - lo) / (knot - lo)\n        elif driver < hi:\n            h = (hi - driver) / (hi - knot)\n    return h\n\n\ndef combo_blend(raw, cdrv, lo, hi, nt):\n    """The combo rule: how a combo target reads its drivers.\n\n    The PRODUCT of every driver, with the LAST keyword in the alias counted\n    TWICE -- `cheekPuffL_noseWrinkleL_jawDrop` reads\n    `cheekPuffL * noseWrinkleL * jawDrop * jawDrop`. That is not a general\n    truth about combos, it is how THIS corpus of combo shapes was sculpted, so\n    it is the rule its sculpts expect. The drivers arrive in alias order, so\n    the last keyword is simply the last entry in the slice.\n\n    This is the one to change if you want a different feel: drop the squaring\n    for a plain product, `min()` over the drivers holds up much sooner, and the\n    geometric mean (`p ** (1.0 / n)`) sits between the two.\n    """\n    p = 1.0\n    for j in range(lo, hi):\n        dr = int(cdrv[j])\n        if dr >= 0 and dr < nt:\n            p = p * float(raw[dr])\n    if hi > lo:\n        dr = int(cdrv[hi - 1])\n        if dr >= 0 and dr < nt:\n            p = p * float(raw[dr])\n    return p\n\n\ndef resolve_morph_weights(raw, ibase, iknot, cofs, cdrv, do_corr, do_combo):\n    """Raw weight[] channels -> the effective weight per target.\n\n    Correctives are ADDITIVE: a target keeps whatever is keyed on its own\n    channel and the driven amount is ADDED on top, so a corrective can be\n    dialled by hand as well as derived. With both switches off this returns the\n    raw channels untouched, which is a plain blendShape.\n\n    Every table read is bounds-clamped. That is load-bearing, not defensive\n    noise: compiled, `nd::at1_ref` does NO bounds checking, so a stale table\n    would be a silent out-of-bounds heap read.\n    """\n    nt = raw.shape[0]\n    nib = ibase.shape[0]\n    nkn = iknot.shape[0]\n    nco = cofs.shape[0]\n    ncd = cdrv.shape[0]\n\n    out = np.zeros(nt)\n    for t in range(nt):\n        e = float(raw[t])\n\n        if do_corr:\n            if t < nib and t < nkn:\n                m = int(ibase[t])\n                if m >= 0 and m < nt:\n                    e = e + inbetween_hat(float(raw[m]), float(iknot[t]), ibase, iknot, m)\n\n        if do_combo:\n            if t + 1 < nco:\n                lo = int(cofs[t])\n                hi = int(cofs[t + 1])\n                if lo < 0:\n                    lo = 0\n                if hi > ncd:\n                    hi = ncd\n                if hi > lo:\n                    e = e + combo_blend(raw, cdrv, lo, hi, nt)\n\n        out[t] = e\n    return out\n'
USER_INPUTS = {"weight": "float", "targetOffset": "int", "targetComponents": "int", "targetDeltas": "double", "interBase": "int", "interKnot": "double", "comboOffset": "int", "comboDriver": "int", "applyCorrectives": "bool", "applyCombos": "bool", "shapeSlot": "int"}
IS_SKIN     = False
TOL         = 1e-3


def _sample(t):
    if t == "bool": return random.choice([0, 1])
    if t == "int": return random.randint(-3, 3)
    if t == "enum": return random.randint(0, 1)
    if t in ("vector", "euler"): return [random.uniform(-2, 2) for _ in range(3)]
    return random.uniform(-2, 2)


def _set(node, attr, t, v):
    if t in ("vector", "euler"):
        cmds.setAttr(node + "." + attr, v[0], v[1], v[2], type="double3")
    else:
        cmds.setAttr(node + "." + attr, v)


def _pts(mesh):
    return cmds.xform(mesh + ".vtx[*]", q=True, os=True, t=True)


def _apply(deformer_type, configure):
    tr = cmds.polySphere(r=1, sx=12, sy=12, ch=False)[0]
    d  = cmds.deformer(tr, type=deformer_type)[0]
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
            v = _sample(t)
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
