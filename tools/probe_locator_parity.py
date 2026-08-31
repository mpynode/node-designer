"""Probe: INTERPRETED vs COMPILED parity for the deterministic draw lowering.

Codegen + a clean compile prove nothing about what the gizmo DRAWS. For each
fixture this:

  1. runs the Python draw expression and harvests ``to_commands()`` -- the
     ground truth the viewport renders today;
  2. builds the same node's ``-DMPYNODE_PROBE`` binary (which runs the LOWERED
     computeBuffers) and reads its JSON dump;
  3. compares the ordered command list element for element.

The Python expression is BOTH the thing under test and the oracle, so there is
no hand-written expected value to drift.

Run with mayapy:
  <mayapy> tools/probe_locator_parity.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
sys.path.insert(0, _HERE)

OUT_DIR = "/tmp/probe_locator_parity"
TOL = 1e-5          # the buffers are float32 on the Python side

# (name, compute) -- each must lower (verified by probe_locator_lowering.py).
FIXTURES = [
    ("p_circle", """
self.draw = DrawCircle(center=(1.0, 2.0, 3.0), radius=2.0, color=(1.0, 0.0, 0.0))
"""),
    ("p_shapes", """
self.draw = (DrawSphere(center=(0.0, 0.0, 0.0), radius=1.0, color=(1.0, 0.0, 0.0))
             + DrawBox(center=(2.0, 0.0, 0.0), radius=0.5, color=(0.0, 1.0, 0.0))
             + DrawCone(center=(4.0, 0.0, 0.0), radius=0.5, filled=False))
"""),
    ("p_points", """
pts = np.zeros((8, 3))
pts[:, 0] = np.arange(8) * 0.5
pts[:, 1] = np.sin(np.arange(8) * 0.7)
self.draw = DrawPoints(pts, color=(0.2, 0.8, 1.0), size=6.0)
"""),
    ("p_lines", """
a = np.zeros((5, 3))
a[:, 0] = np.arange(5) * 1.0
b = a + np.array([0.0, 1.0, 0.0])
self.draw = DrawLines(a, b, color=(1.0, 1.0, 0.0))
"""),
    ("p_curve", """
t = np.linspace(0.0, 6.283185307179586, 16)
ring = np.stack([np.cos(t), np.sin(t), np.zeros(16)], axis=1)
self.draw = DrawCurve(ring, closed=True, color=(1.0, 0.5, 0.0))
"""),
    ("p_mesh", """
pts = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.]])
self.draw = DrawMesh(pts, np.array([4]), np.array([0, 1, 2, 3]),
                     color=(0.2, 0.4, 0.8), cull_backfaces=True)
"""),
    # --- polygon fill modes: color= is PER FACE, uniform_color= is one call ---
    ("p_mesh_face", """
pts = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.],
                [2., 0., 0.], [3., 0., 0.], [3., 1., 0.], [2., 1., 0.]])
fc = np.array([[1., 0., 0., 1.], [0., 0., 1., 1.]])
self.draw = DrawMesh(pts, np.array([4, 4]), np.array([0, 1, 2, 3, 4, 5, 6, 7]),
                     color=fc)
"""),
    ("p_mesh_vert", """
pts = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.]])
vc = np.array([[1., 0., 0., 1.], [0., 1., 0., 1.],
               [0., 0., 1., 1.], [1., 1., 0., 1.]])
self.draw = DrawMesh(pts, np.array([4]), np.array([0, 1, 2, 3]),
                     vertex_colors=vc)
"""),
    ("p_mesh_fv", """
pts = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.]])
fvc = np.array([[1., 0., 0., 1.], [0., 1., 0., 1.],
                [0., 0., 1., 1.], [1., 1., 1., 1.]])
self.draw = DrawMesh(pts, np.array([4]), np.array([0, 1, 2, 3]),
                     face_vertex_colors=fvc)
"""),
    ("p_mesh_unif", """
pts = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.]])
self.draw = DrawMesh(pts, np.array([4]), np.array([0, 1, 2, 3]),
                     uniform_color=(0.3, 0.6, 0.9, 0.5))
"""),
    ("p_mesh_wire", """
pts = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.]])
cube = DrawMesh(pts, np.array([4]), np.array([0, 1, 2, 3]), color=(0.2, 0.4, 0.8))
self.draw = cube.outlined((0.04, 0.05, 0.06, 1.0), width=2.5,
                          boundary_only=True)
"""),
    ("p_mesh_flags", """
pts = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.]])
self.draw = DrawMesh(pts, np.array([4]), np.array([0, 1, 2, 3]),
                     color=(0.2, 0.4, 0.8), world_space=True,
                     highlight_fill=True, highlight_wire=False,
                     precise_hover=True, cull_backfaces=False)
"""),
    # --- per-element colour arrays + world-space lines + an OPEN curve -------
    ("p_pts_percol", """
pts = np.zeros((4, 3))
pts[:, 0] = np.arange(4) * 1.0
cols = np.array([[1., 0., 0., 1.], [0., 1., 0., 1.],
                 [0., 0., 1., 1.], [1., 1., 0., 1.]])
sizes = np.array([2.0, 4.0, 6.0, 8.0])
self.draw = DrawPoints(pts, color=cols, size=sizes)
"""),
    ("p_lines_world", """
a = np.zeros((3, 3))
a[:, 0] = np.arange(3) * 1.0
cols = np.array([[1., 0., 0., 1.], [0., 1., 0., 1.], [0., 0., 1., 1.]])
self.draw = DrawLines(a, a + 1.0, color=cols, world_space=True)
"""),
    ("p_curve_open", """
t = np.linspace(0.0, 3.0, 8)
poly = np.stack([t, np.sin(t), np.zeros(8)], axis=1)
self.draw = DrawCurve(poly, closed=False, color=(0.1, 0.9, 0.3))
"""),
    ("p_text1", """
pts = np.array([[0., 0., 0.], [1., 0., 0.], [2., 0., 0.]])
self.draw = DrawText("tag", pts, color=(1.0, 1.0, 0.0), size=0.8)
"""),
    ("p_textn", """
pts = np.array([[0., 0., 0.], [1., 0., 0.]])
self.draw = DrawText(["lines", "points"], pts, color=(0.2, 0.9, 0.4))
"""),
    # accumulator idiom: a FALSE branch must contribute nothing, and the
    # surviving items must keep their authoring order.
    ("p_accum", """
items = []
if 1.0 > 0.5:
    items.append(DrawCircle(center=(0.0, 0.0, 0.0), radius=1.0, color=(1.0, 0.0, 0.0)))
if 0.0 > 0.5:
    items.append(DrawPoints(np.zeros((3, 3)), color=(0.0, 1.0, 0.0), size=5.0))
items.append(DrawLines(np.zeros((2, 3)), np.ones((2, 3)), color=(0.0, 0.0, 1.0)))
self.draw = items
"""),
    ("p_loop", """
items = []
for i in range(3):
    items.append(DrawCircle(center=(float(i), 0.0, 0.0), radius=1.0,
                            color=(1.0, 0.5, 0.0)))
self.draw = items
"""),
    # --- INIT-tab module constants read as bare names by the compute --------
    ("p_init_scalar", """
self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=TWO_PI * 0.25,
                       color=(1.0, 0.0, 0.0))
""", """
import numpy as np
TWO_PI = 6.283185307179586
"""),
    ("p_init_tuple", """
self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=1.0, color=WIRE_COLOR)
""", """
WIRE_COLOR = (0.04, 0.05, 0.06, 1.0)
"""),
    ("p_init_array", """
self.draw = DrawMesh(CUBE_PTS, CUBE_CNT, CUBE_IDX, color=(0.2, 0.4, 0.8))
""", """
import numpy as np
CUBE_PTS = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.]])
CUBE_CNT = np.array([4])
CUBE_IDX = np.array([0, 1, 2, 3])
"""),
    ("p_init_chain", """
self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=OUTER,
                       color=(0.0, 1.0, 0.0))
""", """
BASE = 2.0
OUTER = BASE * 3.0
"""),
    ("p_init_helper", """
r = scaled(1.5)
self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=r, color=(0.0, 0.0, 1.0))
""", """
GAIN = 2.5


def scaled(x):
    return x * GAIN
"""),
    ("p_init_labels", """
self.draw = DrawText(TEXT_STRINGS, TEXT_POS, color=(1.0, 1.0, 0.0))
""", """
import numpy as np
TEXT_STRINGS = ["lines", "points", "polygons"]
TEXT_POS = np.array([[0., 0., 0.], [0., 1., 0.], [0., 2., 0.]])
"""),
    # --- enum .name() dispatch: the idiom the templates use -----------------
    ("p_enum_name", """
mode = self.shapeMode.name()
if mode == "sphere":
    self.draw = DrawSphere(center=(0.0, 0.0, 0.0), radius=1.0, color=(1.0, 0.0, 0.0))
elif mode == "box":
    self.draw = DrawBox(center=(0.0, 0.0, 0.0), radius=1.0, color=(0.0, 1.0, 0.0))
else:
    self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=1.0, color=(0.0, 0.0, 1.0))
""", "", {"shapeMode": {"type": "enum", "is_array": False,
                        "default_value": 1,
                        "enum_names": ["sphere", "box", "circle"]}}),
    # --- getattr(self, name, default): presence is a COMPILE-TIME fact ------
    ("p_getattr_has", """
r = getattr(self, "radius", 0.25)
self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=r, color=(1.0, 0.0, 0.0))
""", "", {"radius": {"type": "float", "is_array": False,
                     "default_value": 3.0}}),
    ("p_getattr_missing", """
r = getattr(self, "notDeclared", 0.25)
self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=r, color=(0.0, 1.0, 0.0))
"""),
    # --- string INPUT plug as a RUNTIME label -------------------------------
    # The default is NON-empty on purpose: a lowering that dropped the plug and
    # emitted an empty label would still compile, and would still draw the right
    # NUMBER of labels. Only the text tells the two apart.
    ("p_str_plug", """
pts = np.array([[0., 0., 0.], [1., 0., 0.]])
self.draw = DrawText(self.label, pts, color=(1.0, 1.0, 0.0), size=0.8)
""", "", {"label": {"type": "string", "is_array": False,
                    "default_value": "hi"}}),
    ("p_str_concat", """
pts = np.array([[0., 0., 0.]])
self.draw = DrawText("f " + self.label, pts, color=(0.2, 0.9, 0.4))
""", "", {"label": {"type": "string", "is_array": False,
                    "default_value": "hi"}}),
    # A hex escape in a C++ literal is GREEDY, so the baked-in default has to
    # split "\\xc3\\xa9" from the following "a" -- through a real compiler.
    ("p_str_utf8", """
self.draw = DrawText(self.label, (0.0, 0.0, 0.0))
""", "", {"label": {"type": "string", "is_array": False,
                    "default_value": u"éa"}}),
    # --- list(<str>): a RUNTIME label list whose length drives the geometry ---
    ("p_str_chars", """
chars = list(self.label)
n = len(chars)
pts = np.zeros((n, 3))
pts[:, 0] = np.arange(n) * 1.0
self.draw = DrawText(chars, pts, color=(0.9, 0.3, 0.1), size=0.7)
""", "", {"label": {"type": "string", "is_array": False,
                    "default_value": "MPy"}}),
    # Python splits by CODE POINT; a UTF-8 std::string is BYTES. "éa" is TWO
    # labels, not three -- and n also sizes the position array, so a byte split
    # would disagree on the geometry too, not just the text.
    ("p_str_utf8_chars", """
chars = list(self.label)
n = len(chars)
pts = np.zeros((n, 3))
pts[:, 1] = np.arange(n) * 2.0
self.draw = DrawText(chars, pts)
""", "", {"label": {"type": "string", "is_array": False,
                    "default_value": u"éaß"}}),
    # ONE label with MANY positions broadcasts (_strings(value, n)).
    ("p_str_broadcast", """
chars = list(self.label)
self.draw = DrawText(chars, np.zeros((3, 3)), color=(0.1, 0.8, 0.9))
""", "", {"label": {"type": "string", "is_array": False,
                    "default_value": "X"}}),
    # .strip() + the str ternary: the animated_text idiom. A blank plug must
    # fall back, so the two sides disagree unless strip() matches Python.
    ("p_str_strip_blank", """
msg = self.label if self.label.strip() else "fallback"
chars = list(msg)
n = len(chars)
self.draw = DrawText(chars, np.zeros((n, 3)), color=(1.0, 1.0, 0.0))
""", "", {"label": {"type": "string", "is_array": False,
                    "default_value": "   "}}),
    ("p_str_strip_kept", """
msg = self.label if self.label.strip() else "fallback"
self.draw = DrawText(msg.strip(), (0.0, 0.0, 0.0))
""", "", {"label": {"type": "string", "is_array": False,
                    "default_value": "  hi  "}}),
    # --- import spellings: origin resolution, end to end through a compiler ---
    # The interpreted side really executes these imports, so if the lowering
    # resolved any of them to the wrong function the buffers would disagree.
    ("p_alias_shapes", """
v = onp.array([3.0, 4.0, 12.0])
r = norm(v) * 0.1 + s(0.0) + P * 0.0
pts = onp.zeros((2, 3))
pts[:, 0] = onp.arange(2) * c(0.0)
self.draw = [DrawCircle(center=(0.0, 0.0, 0.0), radius=r, color=(0.3, 0.6, 0.9)),
             DrawPoints(pts, color=(1.0, 0.2, 0.2), size=4.0)]
""", """
import numpy as onp
from numpy.linalg import norm
from numpy import sin as s
from math import cos as c
from math import pi as P
"""),
    ("p_order", """
pts = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.]])
self.draw = [DrawCircle(center=(0.0, 0.0, 0.0), radius=1.0, color=(1.0, 0.0, 0.0)),
             DrawMesh(pts, np.array([4]), np.array([0, 1, 2, 3])),
             DrawPoints(pts, color=(0.0, 1.0, 0.0), size=3.0)]
"""),
]


def _shipped_template(name):
    """A fixture built from a SHIPPED .mpn template, not a hand-written snippet.

    The inline fixtures each probe one feature; this runs a real authored gizmo
    end to end, which is the only thing that proves the features compose."""
    import glob
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # The ``templates/*/MPyLocator/...`` glob dated from the basics/advanced
    # layout; a "*" matches no empty component, so once the category level was
    # removed it stopped matching and this fixture silently dropped out.
    hits = glob.glob(os.path.join(root, "templates", "MPyLocator", name,
                                  "template.mpn"))
    if not hits:
        return None
    with open(hits[0]) as fh:
        data = json.load(fh)["data"]
    inputs = {}
    for plug, meta in (data.get("input_attrs") or {}).items():
        meta = dict(meta)
        meta["type"] = meta.pop("attr_type", meta.get("type"))
        inputs[plug] = meta
    return ("t_" + name, data.get("expression") or "",
            data.get("init_source") or "", inputs)


_ANIMATED_TEXT = _shipped_template("Animated Text")
if _ANIMATED_TEXT is not None:
    FIXTURES.append(_ANIMATED_TEXT)
else:
    # Say so LOUDLY. A silently dropped fixture still prints ALL PASS, which
    # reads as "the template is verified" when it was never run.
    print("!! animated_text template not found -- its parity fixture is NOT "
          "running")


class _EnumShim(int):
    """Stand-in for EnumInt: an int whose .name() is the field name. The real
    one resolves through the attribute MObject, which the probe has no scene
    for -- the VALUE semantics are what parity is testing."""

    def __new__(cls, value, names):
        inst = int.__new__(cls, int(value))
        inst._names = list(names)
        return inst

    def name(self):
        return (self._names[int(self)] if 0 <= int(self) < len(self._names)
                else "")


def _seed_inputs(slf, inputs):
    """Give the interpreted `self` the same input values the compiled probe
    starts from: each plug's DEFAULT (what emit_locator bakes into the Inputs
    POD)."""
    for plug, meta in (inputs or {}).items():
        val = meta.get("default_value")
        if meta.get("type") == "enum":
            setattr(slf, plug, _EnumShim(val or 0, meta.get("enum_names") or []))
        elif meta.get("type") == "bool":
            setattr(slf, plug, bool(val))
        else:
            setattr(slf, plug, val)


def _interpreted(compute, init="", inputs=None):
    """Run the draw expression exactly as the interpreted node does: the Init
    tab executes first, in the SAME namespace, so its module-level names are
    bare names to the compute."""
    from mpynode._common.draw import draw_types
    ns = {"np": np}
    ns.update({k: getattr(draw_types, k) for k in draw_types.__all__})
    if init and init.strip():
        exec(init, ns)

    class _Self:
        pass

    slf = _Self()
    _seed_inputs(slf, inputs)
    ns["self"] = slf
    # The compiled probe's Inputs POD starts at wallClock = 0.0; pin the
    # interpreted clock to the same value so a wall-clock animation is compared
    # at ONE instant. (The compiled node's clock origin is the plugin's first
    # frame, not the epoch -- see the wall-clock note in nd_lower.)
    import time as _time_mod
    _orig_time = _time_mod.time
    _time_mod.time = lambda: 0.0
    try:
        exec(compute, ns)
    finally:
        _time_mod.time = _orig_time
    return draw_types.to_commands(getattr(slf, "draw", None))


def _compiled(name, compute, init="", inputs=None):
    """Build + run the probe binary for the lowered node; its JSON frame 0."""
    from mpynode.native import compiler as codegen
    from mpynode.native.compiler.spec_model import PORT_BEGIN
    from mpynode.native.spec.spec_extractor import (
        detect_needs_hover as _detect_needs_hover)
    from mpynode.native.toolchain import toolchain
    from probe_locator_compile import _link_maya_runtime, _probe_bin_dir
    import probe_locator_compile as PLC

    PLC.OUT_DIR = OUT_DIR
    spec = {
        "schema_version": 1, "source_node": name + "1", "mpy_type": "mPyLocator",
        "suggested": {"node_type_name": name, "class_name": name.title().replace("_", ""),
                      "type_id": "0x00070d00", "mpx_base": "MPxLocatorNode",
                      "note": "", "heaviness": "hard"},
        "inputs": inputs or {}, "outputs": {}, "variables": {},
        "compute": compute, "init": init, "affects": "all",
        # the real extractor derives this; the wall-clock binding requires it
        "needs_hover": _detect_needs_hover(compute, init),
        "portability": {"portable": True, "blockers": []}, "commands": [],
    }
    cpp = codegen._generate_locator_cpp(spec, for_port=True)
    if PORT_BEGIN in cpp:
        raise AssertionError("%s did not lower (PORT region kept)" % name)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name + ".cpp")
    with open(path, "w") as fh:
        fh.write(cpp)

    maya = toolchain.default_maya_dir()
    compiler = toolchain.default_compiler()
    _link_maya_runtime(toolchain.maya_lib_dir(maya),
                       toolchain.maya_frameworks_dir(maya))
    exe = os.path.join(_probe_bin_dir(), name + "_probe")
    cmd = toolchain.compile_object_cmd(
        compiler, path, exe, include_dir=toolchain.maya_include_dir(maya))
    cmd = [c for c in cmd if c != "-c"]
    cmd += ["-DMPYNODE_PROBE",
            "-L" + toolchain.maya_lib_dir(maya), "-lOpenMaya", "-lFoundation",
            "-Wl,-rpath," + toolchain.maya_lib_dir(maya),
            "-Wl,-rpath," + toolchain.maya_frameworks_dir(maya)]
    env = toolchain.build_env(compiler) or None
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise AssertionError("%s probe build failed:\n%s" % (name, r.stderr[:3000]))
    run = subprocess.run([exe], capture_output=True, text=True, env=env)
    if run.returncode != 0:
        raise AssertionError("%s probe run failed:\n%s" % (name, run.stderr[:2000]))
    return json.loads(run.stdout)[0]


# Python emits ONE command per authored item holding an N-element buffer; C++
# emits one DrawCmd per PRIMITIVE. Both replay to the same flat sequence, so
# parity is checked on that flattened sequence.
_KIND_INDEX = {"sphere": 0, "circle": 1, "box": 2, "cone": 3, "cylinder": 4}


def _py_elements(commands):
    """Flatten to/commands() into one (slot, payload) per drawn primitive."""
    out = []
    for rec in commands:
        slot, buf = rec["slot"], rec["buffer"]
        if slot == "shapes":
            for k in range(len(buf["centers"])):
                out.append((slot, {
                    "kind": _KIND_INDEX[buf["kinds"][k]],
                    "center": buf["centers"][k], "radius": buf["radii"][k],
                    "axis": buf["axes"][k], "color": buf["colors"][k],
                    "filled": bool(buf["filled"][k])}))
        elif slot == "points":
            for k in range(len(buf["positions"])):
                out.append((slot, {
                    "pos": buf["positions"][k], "color": buf["colors"][k],
                    "size": buf["sizes"][k]}))
        elif slot == "lines":
            for k in range(len(buf["starts"])):
                out.append((slot, {
                    "start": buf["starts"][k], "end": buf["ends"][k],
                    "color": buf["colors"][k]}))
        elif slot == "text":
            for k in range(len(buf["positions"])):
                out.append((slot, {
                    "pos": buf["positions"][k], "color": buf["colors"][k],
                    "size": buf["sizes"][k], "label": buf["strings"][k]}))
        elif slot == "polygons":
            out.append((slot, {
                "points": buf["points"], "indices": buf["indices"],
                "counts": buf["counts"],
                "cull": bool(buf.get("cull_backfaces")),
                "world": bool(buf.get("world_space")),
                "precise": bool(buf.get("precise_hover")),
                "wire": buf.get("wireframe") is not None,
                "wire_color": buf.get("wireframe"),
                "wire_width": buf.get("wireframe_width"),
                "wire_bonly": bool(buf.get("wireframe_boundary_only")),
                "hl_fill": buf.get("highlight_fill"),
                "hl_wire": buf.get("highlight_wire"),
                # exactly one of these four is present -- see _flush_polygons
                "face_colors": buf.get("face_colors"),
                "vertex_colors": buf.get("vertex_colors"),
                "face_vertex_colors": buf.get("face_vertex_colors"),
                "uniform": buf.get("colors")}))
        else:
            raise AssertionError("no comparison rule for slot %r" % slot)
    return out


def _cpp_element(frame, slot, i):
    """The i-th primitive of `slot`, keyed the same way as _py_elements."""
    if slot == "shapes":
        return {"kind": frame["shapeKind"][i], "center": frame["shapeCenter"][i],
                "radius": frame["shapeRadius"][i], "axis": frame["shapeAxis"][i],
                "color": frame["shapeColor"][i],
                "filled": bool(frame["shapeFilled"][i])}
    if slot == "points":
        return {"pos": frame["pointPos"][i], "color": frame["pointColor"][i],
                "size": frame["pointSize"][i]}
    if slot == "lines":
        return {"start": frame["lineStart"][i], "end": frame["lineEnd"][i],
                "color": frame["lineColor"][i]}
    if slot == "text":
        return {"pos": frame["textPos"][i], "color": frame["textColor"][i],
                "size": frame["textSize"][i], "label": frame["textStr"][i]}
    if slot == "polygons":
        pg = frame["polys"][i]
        return {"points": pg["points"], "indices": pg["indices"],
                "counts": pg["counts"], "cull": bool(pg["cull"]),
                "world": bool(pg["worldSpace"]),
                "precise": bool(pg["preciseHover"]),
                "wire": bool(pg["wire"]), "wire_color": pg["wireColor"],
                "wire_width": pg["wireWidth"],
                "wire_bonly": bool(pg["wireBoundaryOnly"]),
                "hl_fill": bool(pg["highlightFill"]),
                "hl_wire": bool(pg["highlightWire"]),
                "colorMode": pg["colorMode"], "uniform": pg["uniform"],
                "faceColors": pg["faceColors"],
                "vertexColors": pg["vertexColors"],
                "faceVertexColors": pg["faceVertexColors"]}
    raise AssertionError("no comparison rule for slot %r" % slot)


_PY_FILL_TO_MODE = {"uniform": 0, "face_colors": 1, "vertex_colors": 2,
                    "face_vertex_colors": 3}
_CPP_FILL_VEC = {1: "faceColors", 2: "vertexColors", 3: "faceVertexColors"}


def _cmp_poly_fill(want, got, tag, fails):
    """Compare the polygon FILL, which the two sides may represent differently.

    Python always materialises a table (a uniform `color=` becomes N identical
    face_colors rows); the lowering collapses a rank-1 tint to one setColor.
    That is only legal when every row is identical, so this checks the
    equivalence instead of skipping -- an unchecked field is a false pass."""
    present = [k for k in _PY_FILL_TO_MODE if want.get(k) is not None]
    if len(present) != 1:
        fails.append("%s expected exactly 1 fill, python has %s" % (tag, present))
        return 0.0
    key = present[0]
    py = np.asarray(want[key], dtype=float).reshape(-1, 4)
    mode = got["colorMode"]

    if mode == 0:
        if py.shape[0] > 1 and not np.allclose(py, py[0], atol=TOL):
            fails.append("%s: cpp collapsed to ONE colour but python's %s "
                         "rows differ" % (tag, key))
            return 0.0
        return _close(py[0], got["uniform"], "%s.fill(uniform)" % tag, fails)

    if _PY_FILL_TO_MODE[key] != mode:
        fails.append("%s fill mode: python %s (%d) != cpp %d"
                     % (tag, key, _PY_FILL_TO_MODE[key], mode))
        return 0.0
    return _close(py, got[_CPP_FILL_VEC[mode]], "%s.fill(%s)" % (tag, key), fails)


def _cmp_poly(want, got, tag, fails):
    worst = 0.0
    for key in ("points", "indices", "counts"):
        worst = max(worst, _close(want[key], got[key],
                                  "%s.%s" % (tag, key), fails))
    for key in ("cull", "world", "precise", "wire", "wire_bonly"):
        if want[key] != got[key]:
            fails.append("%s.%s %r != %r" % (tag, key, want[key], got[key]))
    # highlight_* default to "inherit auto_highlight" on the python side; only
    # an explicitly set flag is comparable.
    for key in ("hl_fill", "hl_wire"):
        if want[key] is not None and bool(want[key]) != got[key]:
            fails.append("%s.%s %r != %r" % (tag, key, want[key], got[key]))
    if want["wire"]:
        worst = max(worst, _close(want["wire_color"], got["wire_color"],
                                  tag + ".wire_color", fails))
        worst = max(worst, _close(want["wire_width"], got["wire_width"],
                                  tag + ".wire_width", fails))
    return max(worst, _cmp_poly_fill(want, got, tag, fails))


def _close(a, b, what, fails):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape:
        fails.append("%s shape %s != %s" % (what, a.shape, b.shape))
        return 0.0
    if a.size == 0:
        return 0.0
    err = float(np.max(np.abs(a - b)))
    if err > TOL:
        fails.append("%s max err %.3e > %.1e" % (what, err, TOL))
    return err


def main():
    worst = 0.0
    fails = []
    for fixture in FIXTURES:
        name, compute = fixture[0], fixture[1]
        init = fixture[2] if len(fixture) > 2 else ""
        inputs = fixture[3] if len(fixture) > 3 else None
        py = _interpreted(compute, init, inputs)
        try:
            frame = _compiled(name, compute, init, inputs)
        except AssertionError as exc:
            print("[%-10s] %s" % (name, exc))
            fails.append(name)
            continue

        cpp_cmds = frame["cmds"]
        flat = _py_elements(py)
        py_slots = [s for s, _ in flat]
        cpp_slots = [s for s, _ in cpp_cmds]
        if py_slots != cpp_slots:
            print("[%-10s] ORDER MISMATCH python=%s cpp=%s"
                  % (name, py_slots, cpp_slots))
            fails.append(name)
            continue

        local = []
        for k, ((slot, want), (_s, index)) in enumerate(zip(flat, cpp_cmds)):
            got = _cpp_element(frame, slot, index)
            tag = "%s[%d]:%s" % (name, k, slot)
            if slot == "polygons":
                worst = max(worst, _cmp_poly(want, got, tag, local))
                continue
            for key in ("center", "axis", "color", "pos", "start", "end",
                        "radius", "size"):
                if key in want:
                    worst = max(worst, _close(want[key], got[key],
                                              "%s.%s" % (tag, key), local))
            for key in ("kind", "filled", "label"):
                if key in want and want[key] != got[key]:
                    local.append("%s.%s %r != %r" % (tag, key, want[key], got[key]))
        if local:
            print("[%-10s] %d MISMATCH(es)" % (name, len(local)))
            for m in local[:6]:
                print("             %s" % m)
            fails.append(name)
        else:
            print("[%-10s] parity OK (%d item(s), %d primitive(s))"
                  % (name, len(py), len(flat)))

    print("=" * 70)
    print("worst error: %.3e (tol %.1e)" % (worst, TOL))
    print("ALL PASS" if not fails else "FAILURES: %s" % ", ".join(sorted(set(fails))))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
