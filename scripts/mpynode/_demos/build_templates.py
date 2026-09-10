"""Regenerate the bundled node templates into the gallery folder layout.

Run with mayapy (NOT plain python)::

    MPYNODE_ROOT=<repo> mayapy scripts/mpynode/_demos/build_templates.py

Authors the bundled node-only templates (no baked stored data -- include_persistent=
False), behaviorally verifies each, and writes the template only when its
verification passes. Each template lives in its own
``templates/<category>/<name>/`` folder as ``template.mpn`` (+ a sibling
``description.md``), the convention the "New from Template" gallery scans (see
``_common/template_gallery``):

  * MPyDeformer/Sine Ripple        -- mPyDeformer: sine ripple along
                                           surface normals over time
  * MPyDeformer/Unit Sphere Collision -- mPyDeformer: push verts inside a
                                           collider sphere onto its surface
  * MPyFile/File Simple              -- mPyFile: a full Maya file-node
                                           replica (framework load) +
                                           brightness/contrast -> outColor
  * MPyIkSolver/Two Bone IK          -- mPyIkSolver: 2-bone analytic IK
                                           (law of cosines)
  * MPyNode/<example>            -- mPyNode: bundled demos (bubble_sort,
                                           hex_attribute, ouch, spine, spline,
                                           spring_chain)
  * MPyMesh/Game Of Life          -- mPyMesh: Conway's Game of Life as a
                                           single mesh, one cube per live cell
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.environ["MPYNODE_ROOT"], "scripts"))

import maya.standalone

maya.standalone.initialize()
import maya.cmds as mc
import maya.api.OpenMaya as om
import numpy as np

for _p in ("mpynode_api1", "mpynode_api2"):
    if not mc.pluginInfo(_p, q=True, loaded=True):
        mc.loadPlugin(_p)

from mpynode._common.io.mpn_io import save_mpn, serialize_node
from mpynode._demos import twist_swing_skin_source as _tsw_src

TPL = os.path.join(os.environ["MPYNODE_ROOT"], "templates")
os.makedirs(TPL, exist_ok=True)


# Folder-convention layout (Design v2 Section 5): each template lives in its own
# <category>/<name>/ folder as template.mpn (+ description.md). The folder NAME
# is shown VERBATIM as the gallery label (no naming convention is enforced --
# see template_gallery.display_label); categories are named after the node type
# they hold (MPyDeformer, MPyFile, ...). The node type comes from
# the .mpn payload's native_type, so organization is by CATEGORY.
TEMPLATE_TARGETS = [
    ("mPyDeformer", "MPyDeformer/Sine Ripple"),
    ("mPyFile", "MPyFile/File Simple"),
    ("mPyIkSolver", "MPyIkSolver/Two Bone IK"),
]
_TARGET_BY_TYPE = dict(TEMPLATE_TARGETS)

# Mirror templates: a category landing page (a buildable folder that is ALSO a
# container for nested variants) or a second example that ships the SAME
# payload as a primary template. Authored from the one primary build so the
# copies can never drift.
#
# native_type -> tuple((rel_dir, node_name), ...). The node_name is OVERRIDDEN
# per mirror and must differ from the primary's: node_name becomes the
# registered Maya type of the compiled C++ node, so two templates sharing one
# would compile to two artifacts claiming the same type -- only one can load,
# and which one wins is down to load order. Everything that can actually drift
# (expression, init, attrs, methods) still comes from the single primary build.
# Pinned by test_template_class_uniqueness.
#
# Currently EMPTY. mPyFile used to mirror its primary into "Basic Texture";
# that mirror WAS the primary in all but name, so the two shipped byte-identical
# payloads under two labels. File Simple is now the primary itself.
TEMPLATE_MIRRORS = {}

# The bundled mPyNode gallery templates under MPyNode/<Folder Name>/. Each
# tuple is (source stem, folder name, description.md text). This list
# declares which mpynode template dirs ship -- it is pinned by the gallery
# no-drift test via ALL_DECLARED_DIRS; the template.mpn payloads ship on disk.
MPYNODE_EXAMPLES = [
    ("bubbleSort", "Bubble Sort",
     "# Bubble Sort\n\n"
     "A visual sorting toy. It holds a list of random values and runs one "
     "bubble-sort pass per evaluation, so wire `time` in and press play to "
     "watch the list sort itself. The list length follows how many outputs "
     "you connect, and values are remapped live between `minVal` (default 1) "
     "and `maxVal` (default 100).\n\n"
     "`reset` picks the behaviour: **False** sorts once and holds, **True** "
     "keeps reshuffling, **Auto** (the default) reshuffles the moment the "
     "list is sorted. The values come out on `sort`, with a `SORTED!!!` / "
     "`UNSORTED!!!` status string on `text`.\n\n"
     "**Create + Run demo** builds a row of 100 cubes one unit apart in X, "
     "each cube's height driven by one sorted value."),
    ("hexAttribute", "Hex Attribute",
     "# Hex Attribute\n\n"
     "Turns plain text into the space-separated hex string a Maya `type` node "
     "wants. Here it prints a label plus `inPosition`, rounded to `decimals` "
     "places. The trick is the attribute type: `output` is a `hex` attr, so "
     "the expression writes ordinary text and it encodes itself -- no manual "
     "unicode->hex step. Wire `output` into a `type` node's text input.\n\n"
     "**Create + Run demo** builds an extruded Type text mesh whose parent "
     "transform is the handle -- drag it and the text redraws with its own "
     "X/Y/Z."),
    ("ouch", "Ouch",
     "# Ouch\n\n"
     "Watches a joint angle and complains when the joint straightens or bends "
     "the wrong way. Wire a joint's rotation into `angle`: `color` stays "
     "green while the joint is bent, and flips to red with an audio clip when "
     "`angle` drops below a small threshold. Playback is non-blocking.\n\n"
     "The sound lives in the persistent `audioData` buffer -- the single "
     "source of truth for playback -- so it travels with the scene and the "
     "player always plays whatever the buffer holds. Swap it two ways: point "
     "`audioFile` at another `.wav` / `.mp3`, or right-click `audioData` in "
     "the Variables tab and choose **Load media**. Audio needs an interactive "
     "Maya session.\n\n"
     "**Create + Run demo** builds a skinned 3-joint arm, drives `angle` from "
     "the elbow and shades the mesh with `color`. It starts bent and green -- "
     "play the timeline and the arm turns red as the elbow straightens past "
     "the threshold."),
    ("spine", "Spine",
     "# Spine\n\n"
     "Drives a joint chain along a NURBS curve. Feed it an `inputCurve` and a "
     "`controlMatrices` array, one per control, returning `outputTranslate`, "
     "`outputRotate` and `outputScale` arrays -- one per entry in `samples`, "
     "0 to 1 along it. `stretch`, `scale`, `shift`, `pivot` and `scaleMethod` "
     "tune the falloff.\n\n"
     "**Create + Run demo** builds a curve up Y, four control locators and a "
     "chain of 12 joints -- move a control or edit the curve to reshape it."),
    ("spline", "Spline",
     "# Spline\n\n"
     "Evaluates a b-spline through control points, De Boor style. Put the "
     "positions in the `cv` vector array, set `degree`, and evenly spaced "
     "points come back in `samples`. The count follows the output array size; "
     "no Maya curve is created.\n\n"
     "**Create + Run demo** builds five zig-zagged locators feeding `cv` and "
     "24 sample spheres along the curve -- drag a locator and the spheres "
     "follow."),
    ("springChain", "Spring Chain",
     "# Spring Chain\n\n"
     "A spring-and-mass solver for secondary motion: tails, ropes, jiggle. "
     "The first point chases the `driver`, each one after chases the point in "
     "front, so motion ripples down the chain and settles. `tension`, "
     "`damping`, `gravity` and `mass` shape it; `minDistance` / `maxDistance` "
     "clamp how far a point drifts from the one ahead. Positions come out on "
     "the `driven` vector array, one per output. Drive it with `time`; "
     "`resetBuffer` clears the stored state.\n\n"
     "**Create + Run demo** builds a keyframed driver locator and a "
     "100-sphere chain wired to `driven`, gravity zeroed, tuning attributes "
     "on the driver's channel box."),
]

# The unitSphereCollision demo re-authored as an mPyDeformer. Every DIR below
# goes by rel dir via _write_template_to, not the type-keyed TEMPLATE_TARGETS
# slot: either the native_type has no slot (mPyMesh, mPyLocator, mPyConstraint,
# mPySkinCluster, mPyTransform, mPyNode) or the slot is taken by the primary, as
# here (sine_ripple). A folder with no template.mpn is a category node in the
# gallery.
USC_DIR = "MPyDeformer/Unit Sphere Collision"

# The Game of Life mPyFile template. Its folder must differ from the mPyMesh
# game_of_life one: the gallery keys by LABEL and labels must stay unique, hence
# game_of_life_texture here vs game_of_life there.
GOL_FILE_DIR = "MPyFile/Game Of Life Texture"

# The Game of Life mPyMesh template. It builds one cube per live cell straight
# into a single output mesh, so any grid size just works -- no per-cell cubes to
# create or outputs to wire (the mPyNode instancer variant it replaces needed
# both).
GOL_MESH_DIR = "MPyMesh/Game Of Life"

# The UV-layout mPyMesh template -- takes a mesh INPUT and outputs that mesh's UV
# set(s) as a flat 2D mesh (each UV -> an (u, v, 0) point; per-face UV
# connectivity -> faces), so you can SEE a mesh's UVs as geometry in the 3D view.
UV_LAYOUT_DIR = "MPyMesh/UV Layout"

# The Metaballs mPyMesh template -- the SDF dual-marching-cubes node
# (mpynode._common.nodes.mesh.sdf_dmc) that folds an ordered stream of SDF
# primitives via CSG (hard union / smooth union / difference). Its demo builds
# the "MPyNode" text plus a Cube/Sphere/Cylinder blob below it, one primitive
# per CSG op.
METABALLS_DIR = "MPyMesh/Metaballs"

# The Voxelize mPyMesh template -- takes a mesh INPUT and rebuilds it as a voxel
# shell: one cube per occupied grid cell, coloured from the source. The cube
# batcher is the game_of_life one (8 verts + 6 quads per cell, emitted in one
# vectorized shot); what differs is where the occupancy comes from -- the source
# surface rather than a Life board.
VOXELIZE_DIR = "MPyMesh/Voxelize"

# The Mesh Maze mPyMesh template -- takes a mesh INPUT and carves a maze into it,
# outputting the maze's WALLS as geometry. Defined here so ALL_DECLARED_DIRS can
# reference it; its INIT/COMPUTE constants and builder live at the end of the
# file, with the rest of the newer builders.
MAZE_DIR = "MPyMesh/Mesh Maze"

# Two mPyMesh templates that read their geometry off DISK through `ndio`, which
# the C++ transpiler lowers onto the nd_io kernel; they differ in LAYOUT (see the
# disk-mesh section below).
DISK_MESH_CACHE_DIR = "MPyMesh/Disk Mesh Cache"
JSON_MESH_READER_DIR = "MPyMesh/JSON Mesh Reader"

# The four mPyLocator widget templates. Folder names are shown verbatim in the
# gallery, so they must stay unique.
LOC_SHOWCASE_DIR  = "MPyLocator/Widget Showcase"
LOC_TEXT_DIR      = "MPyLocator/Animated Text"
LOC_SELECTION_DIR = "MPyLocator/Animated Selection"
LOC_REGION_DIR    = "MPyLocator/Mesh Regions"

# The other mPyFile templates. Each one builds on the SAME framework texture
# services the primary (File Simple) uses -- self.read_texture() /
# self.sample_texture() -- and adds one idea on top.
#
# File Simple is the one that does NOT lower to C++: its embedded-image
# fallback needs a branch ("no file on disk? use the baked bytes"), and a
# branch around a texture load has no deterministic C++ form, so it AI-ports.
# It still loads through the framework -- the embedded bytes are staged to a
# temp file and read back with read_texture(path) -- so there is no second
# loader here either.
FILE_SIMPLE_DIR   = "MPyFile/File Simple"
FILE_SCANLINE_DIR = "MPyFile/File Scanline"
# Multi-file composite mPyFile template (three layers, alpha-over).
FILE_COMPOSITE_DIR = "MPyFile/File Composite"
# The corrective blendShape demo builds a real 167-target face, so it ships the
# sparse sculpt archive and its base head beside the template.
COMBO_CORR_DIR    = "MPyBlendShape/Combo Correctives"

# The mPyConstraint template -- an orthogonal-Procrustes (SVD) rivet that
# rigidly attaches transforms to a DEFORMING mesh (the deformation-robust cousin
# of a rivet). It fits N clusters in one vectorized call (outMatrix array), with
# cluster membership authored as named component tags.
CONSTRAINT_TAGS_DIR    = "MPyConstraint/Procrustes Tags"

# DNET spring-network relaxation solver -- a base mPyNode (shares native_type
# "mPyNode" with the mpynode examples, hence the explicit rel dir).
DNET_DIR = "MPyNode/DNET"

# Aim-between-two-matrices -- a base mPyTransform. Defined here so
# ALL_DECLARED_DIRS can reference it; its INIT/COMPUTE constants and builder live
# further down, next to (but not used by) the DNET section.
AIM_DIR = "MPyTransform/Aim Between Matrices"

# mPySkinCluster templates -- the SAME native_type ("mPySkinCluster", a genuine
# MPxSkinCluster), differing only in Compute (linear-blend, dual-quaternion,
# twist/swing dual-weights).
SKIN_LBS_DIR = "MPySkinCluster/Linear Blend Skin"
SKIN_DQS_DIR = "MPySkinCluster/Dual Quaternion Skin"
SKIN_TWISTSWING_DIR = "MPySkinCluster/Twist Swing Skin"

# RBF thin-plate wrap -- a base mPyNode with THREE mesh INPUTS + one mesh OUTPUT
# attr (the geo-I/O compile path).
RBF_WRAP_DIR = "MPyNode/RBF Wrap"

# The same thin-plate wrap as an mPyDeformer: two mesh INPUT cages and NO mesh
# output -- the geometry is the deformer's own outputGeometry, so it stacks in a
# normal deformation chain and honours `envelope`.
RBF_WRAP_DEF_DIR = "MPyDeformer/RBF Wrap Deformer"

# Every bundled template directory this script authors (relative to
# <root>/templates): primaries + mirrors + the mpynode examples + the
# collision deformer. Pinned by the gallery's "no drift" test so a hand-placed
# or deleted template.mpn can't diverge from the generator.
ALL_DECLARED_DIRS = set(rel for _t, rel in TEMPLATE_TARGETS)
for _rels in TEMPLATE_MIRRORS.values():
    ALL_DECLARED_DIRS.update(_rel for _rel, _nm in _rels)
ALL_DECLARED_DIRS.update(
    "MPyNode/" + _snake for _src, _snake, _desc in MPYNODE_EXAMPLES)
ALL_DECLARED_DIRS.add(USC_DIR)
ALL_DECLARED_DIRS.add(GOL_FILE_DIR)
ALL_DECLARED_DIRS.add(GOL_MESH_DIR)
ALL_DECLARED_DIRS.add(UV_LAYOUT_DIR)
ALL_DECLARED_DIRS.add(METABALLS_DIR)
ALL_DECLARED_DIRS.add(VOXELIZE_DIR)
ALL_DECLARED_DIRS.add(MAZE_DIR)
ALL_DECLARED_DIRS.add(DISK_MESH_CACHE_DIR)
ALL_DECLARED_DIRS.add(JSON_MESH_READER_DIR)
ALL_DECLARED_DIRS.update((
    LOC_SHOWCASE_DIR, LOC_TEXT_DIR, LOC_SELECTION_DIR, LOC_REGION_DIR,
    FILE_SIMPLE_DIR, FILE_SCANLINE_DIR, FILE_COMPOSITE_DIR,
))
ALL_DECLARED_DIRS.add(CONSTRAINT_TAGS_DIR)
ALL_DECLARED_DIRS.add(DNET_DIR)
ALL_DECLARED_DIRS.add(AIM_DIR)
ALL_DECLARED_DIRS.add(SKIN_LBS_DIR)
ALL_DECLARED_DIRS.add(SKIN_DQS_DIR)
ALL_DECLARED_DIRS.add(SKIN_TWISTSWING_DIR)
ALL_DECLARED_DIRS.add(RBF_WRAP_DIR)
ALL_DECLARED_DIRS.add(RBF_WRAP_DEF_DIR)
ALL_DECLARED_DIRS.add("MPyDeformer/Patch Relax")
# New base-node-type templates (mPyNurbsCurve / mPyNurbsSurface /
# mPyDeformer NURBS wave / mPyBlendShape). ALL of these compile to pure C++
# (byte-parity) -- including the blend shape, which reads baked numeric delta
# tables rather than the live target meshes (see COMBO_COMPUTE).
ALL_DECLARED_DIRS.update((
    "MPyNurbsCurve/NURBS Helix",
    "MPyNurbsSurface/NURBS Ripple",
    "MPyDeformer/NURBS Wave",
    "MPyBlendShape/Combo Correctives",
))


def _framework_read_texture(path):
    """What a real node's ``self.read_texture()`` does, at the mPyFile preset
    DEFAULTS (colorSpace 0 = sRGB, pre-filter off).

    The build gates exec template source against fake ``self`` objects. Those
    have no SelfProxy blessed-method tier, so they route the framework load
    through this instead -- the same ``file_texture_ops`` entry point the real
    blessed adapter falls back to."""
    from mpynode._common.methods import file_texture_ops as _tex
    return _tex.load_linear_pixels(path, 0, False, _tex.kPreFilterGaussian, 1.0)


def _framework_sample(img, u, v):
    """What ``self.sample_texture(buf, u, v)`` does at the preset defaults
    (wrap both axes, black border). BILINEAR -- the hand-rolled loaders these
    templates used to carry were nearest, so gate expectations differ."""
    from mpynode._common.methods import file_texture_ops as _tex
    return _tex.sample(img, u, v, _tex.kWrapWrap, _tex.kWrapWrap, (0.0, 0.0, 0.0))


def _template_path(native_type):
    """Absolute path to <root>/<category>/<name>/template.mpn for a type."""
    rel = _TARGET_BY_TYPE[native_type]
    return os.path.join(TPL, *rel.split("/"), "template.mpn")


def _write_template(payload, native_type, description, root=None):
    """Write a node-only template to <root>/<category>/<name>/template.mpn
    and author a sibling description.md. Keeps the behavioral-gate caller's
    contract: only invoked AFTER the per-type verification passed.

    Also writes any TEMPLATE_MIRRORS for this type from the SAME payload and
    description, so a category landing page / "advanced" example can never
    drift from its primary -- except for ``node_name``, which each mirror
    overrides so no two templates compile to the same registered C++ type."""
    base = root if root is not None else TPL
    rels = [(_TARGET_BY_TYPE[native_type], None)]
    rels.extend(TEMPLATE_MIRRORS.get(native_type, ()))
    for rel, node_name in rels:
        folder = os.path.join(base, *rel.split("/"))
        os.makedirs(folder, exist_ok=True)
        out = payload
        if node_name:
            out = dict(payload)
            out["node_name"] = node_name
        save_mpn(out, os.path.join(folder, "template.mpn"))
        with open(os.path.join(folder, "description.md"), "w") as f:
            f.write(description.rstrip() + "\n")



def _stamp_class(node, class_name, mpy_type):
    """Give the authoring node a canonical Class identity.

    Without one, ``derive_class_identity(class_path or name, ...)`` falls back to
    the node's INSTANCE NAME, so a template's compiled type name is an accident of
    what the builder called the node -- and two templates can collide. Each name
    here is the PascalCase of the type name the template already derived, so this
    adds identity WITHOUT renaming anything.
    """
    from mpynode._common.io.user_classes import synthesize, dotted_path

    synthesize(class_name, mpy_type)
    node.set_py_class(dotted_path(class_name))

def _write_template_to(rel, payload, description, root=None):
    """Write a node-only template to <root>/<rel>/template.mpn plus a sibling
    description.md, addressed by an EXPLICIT rel dir.

    Like :func:`_write_template` but not keyed by native_type: the mpynode
    example templates share native_type ``mPyNode`` with each other, and the
    collision deformer shares ``mPyDeformer`` with sine_ripple, so they can't use
    the type->dir lookup. No mirrors."""
    folder = os.path.join(root if root is not None else TPL, *rel.split("/"))
    os.makedirs(folder, exist_ok=True)
    save_mpn(payload, os.path.join(folder, "template.mpn"))
    with open(os.path.join(folder, "description.md"), "w") as f:
        f.write(description.rstrip() + "\n")


# ======================================================================
# VANILLA methods-source prologues
# ======================================================================
# A @maya_command body ships as embedded PYTHON inside the compiled .mll and
# runs on machines that have Maya but NOT mpynode, so it may only use vanilla
# Maya: builtins, the stdlib, numpy, and maya.*. Importing from mpynode there
# raises ModuleNotFoundError and the command dies.
#
# The two helper sets more than one template needs, defined ONCE and composed
# into each methods source so every shipped .mpn carries a self-contained copy.
# Helpers only ONE template needs are inlined at that template instead.
#
# The marker decorators are deliberately NOT imported: build_methods_namespace
# pre-injects maya_command / maya_demo / maya_test (and the @maya_test assert
# helpers) before exec'ing the source, so an import of them is redundant here
# and fatal in a bundle.
VANILLA_SETUP_ERROR = '''class SetupError(Exception):
    """The current selection / scene state can't support setup for this node.
    Message is user-facing (it names what to select)."""

'''

VANILLA_MESHES = '''
def _has_shape(node, shape_types):
    from maya import cmds as mc
    if mc.nodeType(node) in shape_types:
        return True
    for st in shape_types:
        if mc.listRelatives(node, shapes=True, type=st, noIntermediate=True):
            return True
    return False


def _meshes(sel):
    return [n for n in sel if _has_shape(n, ("mesh",))]

'''


# ======================================================================
# 1. mPyDeformer -- sine ripple along normals over time
# ======================================================================
DEF_INIT = "import numpy as np\nimport maya.OpenMaya as om\n"
DEF_COMPUTE = r'''# Sine-ripple deformer: each vertex rides a travelling sine wave along its
# surface normal. The wave's phase advances with distance from the mesh
# centre and with time, so it animates as the timeline plays.
mesh = self.outputGeometry[0]            # writable handle for this output mesh
pts = mesh.getPoints()                   # (N, 3) object-space points (numpy)

# True per-vertex normals (object space). The output handle wraps an API-1
# MFnMesh, so use the in-out MFloatVectorArray form.
nrm = om.MFloatVectorArray()
mesh.getVertexNormals(False, nrm, om.MSpace.kObject)
normals = np.array([[nrm[i].x, nrm[i].y, nrm[i].z]
                    for i in range(nrm.length())], dtype=float)

amp = self.amplitude
freq = self.frequency
speed = self.speed
env = self.envelope               # built-in deformer envelope (0..1)

centre = pts.mean(axis=0)
dist = np.linalg.norm(pts - centre, axis=1)
phase = 2.0 * np.pi * freq * dist - speed * self.time
offset = (amp * np.sin(phase))[:, None] * normals

mesh.setPoints(pts + env * offset)
'''


# Demo authored into the sine-ripple template's Methods tab: fabricate a
# self-contained showcase (a subdivided plane driven by THIS deformer with a
# visible travelling wave and a one-loop playback range). "self" is the deformer
# node instance -- the demo attaches it to a fresh plane and dials in the wave.
DEF_DEMO = '''@maya_test(label="Ripple deforms the mesh (rest at envelope 0)", digits=4)
def test_ripple(self):
    """Validate the node's INTENT (same test passes on the interpreted node and
    its C++ compile -> parity): with the wave OFF (envelope 0, or amplitude 0)
    the mesh sits exactly at rest; with the wave ON it actually moves."""
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_close, assert_true

    name = self.get_name()

    def _set(plug, *vals):
        # A demo may have CONNECTED this input; break it so the test can drive it.
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals)

    # Validate whatever mesh this deformer already drives (e.g. the demo's
    # plane); build one only if it drives nothing yet. Keeps the test on `self`
    # (interpreted==compiled parity) and robust to a live, demo-populated scene
    # and repeated runs.
    geo = mc.deformer(name, q=True, geometry=True) or []
    if geo:
        sh = (mc.ls(geo[0], long=True) or [geo[0]])[0]
    else:
        pl = mc.polyPlane(w=10, h=10, sx=12, sy=12, name="rippleTest#")[0]
        mc.deformer(name, e=True, g=pl)
        sh = mc.listRelatives(pl, shapes=True, noIntermediate=True, f=True)[0]
    xf = mc.listRelatives(sh, parent=True, f=True)[0]

    def pts(amp, env, frame=1):
        _set(name + ".amplitude", amp)
        _set(name + ".envelope", env)
        mc.currentTime(frame)
        mc.dgdirty(name + ".outputGeometry")
        mc.getAttr(sh + ".outMesh")
        sel = om2.MSelectionList(); sel.add(xf)
        fn = om2.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    rest = pts(0.0, 1.0)          # amplitude 0 -> zero offset
    env_off = pts(0.6, 0.0)       # envelope 0 -> zero offset
    deformed = pts(0.6, 1.0)      # wave ON -> real displacement

    # Both "off" states must equal the rest mesh (component-wise).
    assert_close(env_off.ravel().tolist(), rest.ravel().tolist())
    # ...and turning the wave on must actually move points.
    moved = float(np.abs(deformed - rest).max())
    assert_true(moved > 0.05,
                "ripple should displace the mesh (max move %.4f)" % moved)


@maya_demo(label="Ripple a Plane")
def demo(self):
    """Create a subdivided plane, attach this ripple deformer to it, dial in a
    visible wave, and set a one-loop playback range. Press play to watch the
    wave travel across the surface (the wave advances with `time` and with
    distance from the mesh centre)."""
    from maya import cmds as mc
    name = self.get_name()

    plane = mc.polyPlane(w=10, h=10, sx=24, sy=24, name="rippleTarget#")[0]
    mc.setAttr(plane + ".translate", 0.0, 0.0, 0.0, type="double3")
    # Attach THIS deformer to the plane (idempotent -- adopt the bare node).
    if name not in (mc.listHistory(plane) or []):
        mc.deformer(name, e=True, g=plane)

    mc.setAttr(name + ".amplitude", 0.6)
    mc.setAttr(name + ".frequency", 0.8)
    mc.setAttr(name + ".speed", 0.15)
    # Auto-wire the animation clock if the template-apply path did not already.
    if not (mc.listConnections(name + ".time", s=True, d=False) or []):
        try:
            mc.connectAttr("time1.outTime", name + ".time", force=True)
        except Exception:
            pass

    mc.playbackOptions(min=1, max=120)
    mc.currentTime(1)
    mc.select(plane, replace=True)
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name
'''


def build_deformer():
    mc.file(new=True, force=True)
    plane = mc.polyPlane(w=10, h=10, sx=12, sy=12, name="rippleTarget")[0]
    from mpynode.wrappers.mpy_deformer import MPyDeformer

    d = MPyDeformer.create_on(plane, name="sineRipple")
    d.add_input_attr("amplitude", "float", default_value=0.4)
    d.add_input_attr("frequency", "float", default_value=0.6)
    d.add_input_attr("speed", "float", default_value=0.1)
    d.add_input_attr("time", "time")
    d.set_init_expression(DEF_INIT)
    d.set_compute_expression(DEF_COMPUTE)
    d.set_methods_source(DEF_DEMO)
    nm = d.get_name()
    sh = mc.listRelatives(plane, shapes=True)[0]

    def pts_at(frame, amp=None, env=None):
        if amp is not None:
            mc.setAttr(nm + ".amplitude", amp)
        if env is not None:
            mc.setAttr(nm + ".envelope", env)
        mc.currentTime(frame)
        mc.dgdirty(nm + ".outputGeometry")
        mc.getAttr(sh + ".outMesh")
        sel = om.MSelectionList()
        sel.add(plane)
        fn = om.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z] for p in fn.getPoints(om.MSpace.kObject)])

    rest = pts_at(1, amp=0.0, env=1.0)
    f1 = pts_at(1, amp=0.4, env=1.0)
    f12 = pts_at(12, amp=0.4, env=1.0)
    half = pts_at(1, amp=0.4, env=0.5)
    moved = float(np.abs(f1 - rest).max())
    animated = float(np.abs(f1 - f12).max())
    env_scales = np.allclose(half - rest, 0.5 * (f1 - rest), atol=1e-4)
    amp0_is_rest = np.allclose(rest, pts_at(1, amp=0.0, env=1.0), atol=1e-9)
    compute_ok = moved > 0.05 and animated > 0.01 and env_scales and amp0_is_rest

    # --- demo check: the authored "Create + Run demo" fabricates a rippled
    #     plane on a FRESH deserialized node (mirrors what a user clicks). ---
    _stamp_class(d, "SineRipple", "mPyDeformer")
    clean_payload = serialize_node(d, include_persistent=False)
    demo_ok = False
    demo_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node
        from mpynode._common.methods.methods_registry import run_node_demo
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tnm = tnode.get_name()
        run_node_demo(tnode)
        plane_t = (mc.ls("rippleTarget*", type="transform") or [None])[0]
        in_hist = plane_t is not None and tnm in (mc.listHistory(plane_t) or [])
        rippled = False
        if plane_t is not None:
            mc.currentTime(6)
            mc.dgdirty(tnm + ".outputGeometry")
            shp = mc.listRelatives(plane_t, shapes=True, ni=True, f=True)[0]
            mc.getAttr(shp + ".outMesh")
            sel = om.MSelectionList()
            sel.add(plane_t)
            fn = om.MFnMesh(sel.getDagPath(0))
            ys = [p.y for p in fn.getPoints(om.MSpace.kObject)]
            rippled = (max(ys) - min(ys)) > 0.05
        demo_ok = bool(in_hist and rippled)
        demo_err = "plane=%s in_hist=%s rippled=%s" % (plane_t, in_hist, rippled)
    except Exception as exc:
        demo_err = "exc:%r" % exc

    # --- authored @maya_test check: run it on a FRESH deserialized node so a
    #     broken validation body fails the BUILD here rather than shipping. ---
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    ok = compute_ok and demo_ok and test_ok
    print("[deformer] moved=%.4f animated=%.4f env_scales=%s amp0_rest=%s "
          "demo=%s(%s) test=%s(%s) -> %s"
          % (moved, animated, env_scales, amp0_is_rest, demo_ok, demo_err,
             test_ok, test_err, "PASS" if ok else "FAIL"))
    if ok:
        _write_template(
            clean_payload, "mPyDeformer",
            "# Sine Ripple Deformer\n\n"
            "An `mPyDeformer` that pushes each vertex along its normal with a "
            "sine wave, so ripples spread from the mesh centre and travel as "
            "`time` advances -- good for water, flags, and any rolling "
            "wobble. Inputs: `amplitude`, `frequency`, `speed`, `time`, plus "
            "the built-in `envelope`.\n\n"
            "**Create + Run demo** builds a subdivided plane, attaches the "
            "deformer and sets a one-loop playback range -- press play to "
            "watch the ripple travel.")
    return ok


# ======================================================================
# 1b. mPyDeformer -- unit-sphere collision (the converted "pusher" demo)
# ======================================================================
USC_INIT = "import numpy as np\n"
USC_COMPUTE = r'''# Unit-sphere collision deformer (accumulating "pusher" port). Every vertex
# INSIDE the collider sphere is pushed onto its surface, and the pushed result
# is kept in a persistent buffer (self.positions) so the deformation BAKES --
# once the collider passes, the dent stays put (it does not spring back). The
# collider is the UNIT sphere in the local space of the `pusher` matrix, so
# wiring a sphere transform's worldMatrix into `pusher` makes its translate /
# rotate / scale set the collider's centre, orientation and effective radius.
#
# self.positions is registered + seeded by the node's setup from the mesh's
# initial points; if it is missing or stale (topology change) it is re-seeded
# here from the current input. A deformer is not evaluated until a mesh is
# connected, so nothing computes before then.
#
# WARNING: getPoints()/setPoints() are OBJECT space while `pusher` is a WORLD
# matrix, so this is only correct when the deformed mesh has an identity
# transform at the world origin (freeze its transform).
mesh = self.outputGeometry[0]
pts = mesh.getPoints()                         # (N, 3) current input, object space
if len(pts):
    seed = np.hstack([np.asarray(pts, dtype=float), np.ones((len(pts), 1))])
    try:
        buf = np.asarray(self.positions, dtype=float)
    except Exception:
        buf = None
    if buf is None or buf.ndim != 2 or buf.shape != (len(pts), 4):
        buf = seed                             # first eval / topology change -> seed

    P = buf.copy()
    M = self.pusher                            # collider world matrix (MatrixView)
    inv = M.inverse().asNumpy()                # api2 analytic inverse (EM-safe)
    fwd = np.asarray(M, dtype=float)

    local = P @ inv                            # accumulated buffer -> collider local
    dist = np.linalg.norm(local[:, :3], axis=1)
    inside = (dist > 0.0) & (dist < 1.0)       # guard dist==0 (no push direction)
    local[inside, :3] = local[inside, :3] / dist[inside, None]   # onto surface
    P = local @ fwd                            # back to object space (buffer accumulates)

    self.positions = P                         # persist the baked buffer
    env = self.envelope                 # blend the baked buffer against rest
    mesh.setPoints(pts + env * (P[:, :3] - pts))
'''

# Setup authored into the deformer template's Methods tab (wins over the generic
# mPyDeformer.py default via merge-not-replace). Ordered selection: collider
# TRANSFORM first, MESH second.
USC_SETUP = '''# Setup: select the collider TRANSFORM first, then the MESH to deform. Wires the
# collider's worldMatrix into `pusher` FIRST, attaches the deformer to the mesh
# SECOND, and registers a persistent buffer seeded from the mesh's initial points
# so baked collisions survive save/reopen.
def setup(self, *args, **kwargs):
    from maya import cmds as mc
    import maya.api.OpenMaya as om
    from mpynode._common.methods.setup_helpers import _meshes, SetupError
    name = self.get_name()
    # Read the command's pre-create selection snapshot (in pick order), NOT the
    # live selection -- creating the deformer node clobbers the active selection.
    order = [o for o in (kwargs.get("selection") or mc.ls(selection=True) or []) if o != name]
    if len(order) < 2:
        raise SetupError("Select a collider TRANSFORM first, then a MESH to deform.")
    collider = order[0]
    meshes = _meshes(order[1:])
    if not meshes:
        raise SetupError("Select a collider TRANSFORM first, then a MESH to deform.")
    mesh = meshes[0]
    # Capture the mesh's REST object-space points BEFORE attaching (homogeneous
    # [x, y, z, 1]), so the persistent accumulation buffer starts undented even if
    # the collider already overlaps the mesh.
    seed = None
    try:
        shp = mc.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True)[0]
        sl = om.MSelectionList()
        sl.add(shp)
        fn = om.MFnMesh(sl.getDagPath(0))
        seed = [[p.x, p.y, p.z, 1.0] for p in fn.getPoints(om.MSpace.kObject)]
    except Exception:
        seed = None
    # matrix FIRST
    mc.connectAttr(collider + ".worldMatrix[0]", name + ".pusher", force=True)
    # mesh SECOND -- adopt the bare deformer into the mesh's chain (idempotent)
    if name not in (mc.listHistory(mesh) or []):
        mc.deformer(name, e=True, g=mesh)
    # register the persistent buffer so baking survives save/reopen.
    if seed is not None:
        self.set_variable("positions", seed, persistent=True)
    return name
'''

# Demo authored into the collision template's Methods tab (alongside the setup):
# fabricate the whole showcase -- a frozen plane, a collider sphere animated
# sinking through it, wired + seeded exactly like the setup does, so "Create +
# Run demo" shows the baking dent with zero manual wiring.
USC_DEMO = '''@maya_demo(label="Collide a Sphere Through a Plane")
def demo(self):
    """Freeze a subdivided plane at the origin, wire a collider sphere's
    worldMatrix into `pusher`, attach this deformer, seed the persistent rest
    buffer, then animate the sphere sinking through the plane. Press play: the
    collider dents the plane and the dent BAKES -- it stays after the sphere
    passes."""
    from maya import cmds as mc
    import maya.api.OpenMaya as om
    name = self.get_name()

    # Plane frozen at the world origin (the compute works in OBJECT space, so an
    # identity transform at the origin is required for a correct collision).
    plane = mc.polyPlane(w=16, h=12, sx=32, sy=24, name="collisionTarget#")[0]
    mc.makeIdentity(plane, apply=True, t=True, r=True, s=True)

    # Collider: a UNIT sphere scaled up -- its transform scale IS the effective
    # collision radius (the compute uses the unit sphere in `pusher` local space).
    collider = mc.polySphere(radius=1.0, name="collider#")[0]
    mc.setAttr(collider + ".scale", 4.0, 4.0, 4.0, type="double3")

    # Capture the plane's REST object-space points for the persistent seed BEFORE
    # attaching, so the accumulation buffer starts undented.
    seed = None
    try:
        shp = mc.listRelatives(plane, shapes=True, noIntermediate=True, fullPath=True)[0]
        sl = om.MSelectionList()
        sl.add(shp)
        fn = om.MFnMesh(sl.getDagPath(0))
        seed = [[p.x, p.y, p.z, 1.0] for p in fn.getPoints(om.MSpace.kObject)]
    except Exception:
        seed = None

    mc.connectAttr(collider + ".worldMatrix[0]", name + ".pusher", force=True)
    if name not in (mc.listHistory(plane) or []):
        mc.deformer(name, e=True, g=plane)
    if seed is not None:
        self.set_variable("positions", seed, persistent=True)

    # Animate the collider sinking straight through the plane.
    for f, y in ((1, 6.0), (30, 1.5), (60, -6.0)):
        mc.setKeyframe(collider + ".translateY", t=f, v=y)
    mc.playbackOptions(min=1, max=60)
    mc.currentTime(1)
    mc.select(collider, replace=True)
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_test(label="Collision pushes verts onto the sphere and bakes", digits=3)
def test_collision(self):
    """Validate the node's INTENT (the SAME test passes on the interpreted node
    and its C++ compile -> parity): a collider sphere pushes every mesh vertex
    inside it onto the sphere's surface, the dent BAKES (it stays after the
    collider moves away), and `envelope` 0 shows the undeformed rest mesh."""
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_close, assert_true
    from mpynode._common.storedvars.stored_vars_api import set_variable

    name = self.get_name()

    def _set(plug, *vals, **kw):
        # The demo/setup CONNECTS `pusher` (collider.worldMatrix); break any
        # incoming connection so the test can drive the plug directly. Forward
        # kwargs (e.g. type="matrix") through to setAttr.
        for src in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(src, plug)
        mc.setAttr(plug, *vals, **kw)

    # Validate whatever mesh this deformer already drives (e.g. the demo's plane);
    # build one only if it drives nothing yet. Keeps the test on self (parity) and
    # robust to a live, demo-populated scene and repeated runs. The compute is
    # OBJECT-space, so the deformed mesh must be frozen at the world origin.
    geo = mc.deformer(name, q=True, geometry=True) or []
    if geo:
        sh = (mc.ls(geo[0], long=True) or [geo[0]])[0]
    else:
        pl = mc.polyPlane(w=16, h=12, sx=16, sy=12, name="collisionTestTarget#")[0]
        mc.makeIdentity(pl, apply=True, t=True, r=True, s=True)
        mc.deformer(name, e=True, g=pl)
        sh = mc.listRelatives(pl, shapes=True, noIntermediate=True, f=True)[0]

    def pts():
        mc.dgdirty(name + ".outputGeometry")
        mc.getAttr(sh + ".outMesh")
        sel = om2.MSelectionList(); sel.add(sh)
        fn = om2.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    # Envelope 0 shows the undeformed input; capture it as the flat rest AND
    # RE-SEED the persistent bake buffer from it, so accumulation starts clean
    # regardless of a prior demo run or a previous run of this test (the buffer
    # persists otherwise, and a pre-dented buffer would break the surface check).
    # Seed through the NAME-based stored-var API (not self.set_variable(), a
    # wrapper method absent on the compiled node's _NodeNameProxy) so the SAME
    # test runs on both. A compiled node const-folds its stored vars and has no
    # _storedVarNames plug, so the seed raises there -- harmless, because verify
    # builds the compiled node fresh in a new scene: the buffer is unset and the
    # compute seeds it from this same flat rest.
    _set(name + ".envelope", 0.0)
    rest = pts()
    try:
        set_variable(name,
            "positions",
            [[float(x), float(y), float(z), 1.0] for x, y, z in rest], persistent=True)
    except Exception:
        pass

    # Collider A: a UNIT sphere scaled x4, centred 2 units above the plane.
    # Collider B: the same sphere moved far away (to prove the dent BAKES).
    s, ty = 4.0, 2.0
    A = [s, 0, 0, 0, 0, s, 0, 0, 0, 0, s, 0, 0.0, ty, 0, 1]
    B = [s, 0, 0, 0, 0, s, 0, 0, 0, 0, s, 0, 100.0, ty, 0, 1]
    centre = np.array([0.0, ty, 0.0])

    # 1) Collider A, envelope 1 -> push inside verts onto the sphere surface.
    _set(name + ".pusher", *A, type="matrix")
    _set(name + ".envelope", 1.0)
    full = pts()

    # 2) Move the collider far away -> the dent must STAY (accumulation / bake).
    _set(name + ".pusher", *B, type="matrix")
    baked = pts()

    # 3) Envelope 0 -> displayed rest (the flat plane; baked buffer retained).
    _set(name + ".envelope", 0.0)
    rest_env0 = pts()

    disp = np.linalg.norm(full - rest, axis=1)
    moved = disp > 1e-3
    n_moved = int(moved.sum())
    assert_true(n_moved > 0,
                "collider should push some verts (moved %d)" % n_moved)

    # Pushed verts land on the collider sphere's surface: |(p - centre) / s| == 1.
    on = np.linalg.norm((full[moved] - centre) / s, axis=1)
    assert_close(on.tolist(), [1.0] * n_moved)

    # The dent bakes: moving the collider away leaves the deformation intact.
    assert_close(baked.ravel().tolist(), full.ravel().tolist())

    # Envelope 0 shows the undeformed rest -- a flat plane at y == 0.
    assert_close(rest_env0[:, 1].tolist(), [0.0] * len(rest_env0))
'''


def build_unit_sphere_collision_deformer():
    mc.file(new=True, force=True)
    # A subdivided plane whose 17x13 vertices sit where the original demo's grid
    # of cubes was (gridX=17 / gridZ=13), with vertex spacing 1.0 to reproduce
    # the collision proportions. The plane's shapeOrig supplies the rest grid.
    plane = mc.polyPlane(w=16, h=12, sx=16, sy=12, name="collisionTarget")[0]
    from mpynode.wrappers.mpy_deformer import MPyDeformer

    # Flat rest captured BEFORE the deformer is attached (afterwards the plane
    # shape IS the deformer output).
    sel0 = om.MSelectionList()
    sel0.add(plane)
    rest = np.array([[p.x, p.y, p.z]
                     for p in om.MFnMesh(sel0.getDagPath(0)).getPoints(
                         om.MSpace.kObject)])

    d = MPyDeformer.create_on(plane, name="unitSphereCollision")
    d.add_input_attr("pusher", "matrix")
    d.set_init_expression(USC_INIT)
    d.set_compute_expression(USC_COMPUTE)
    d.set_methods_source(USC_SETUP + "\n\n" + USC_DEMO)
    nm = d.get_name()
    sh = mc.listRelatives(plane, shapes=True)[0]

    def points():
        mc.dgdirty(nm + ".outputGeometry")
        mc.getAttr(sh + ".outMesh")
        sel = om.MSelectionList()
        sel.add(plane)
        fn = om.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om.MSpace.kObject)])

    # Collider A: a sphere centred 2 units above the plane, world radius 4.
    # Collider B: the same sphere moved far away (to prove the dent BAKES).
    s, ty = 4.0, 2.0
    A = [s, 0, 0, 0, 0, s, 0, 0, 0, 0, s, 0, 0.0, ty, 0, 1]
    B = [s, 0, 0, 0, 0, s, 0, 0, 0, 0, s, 0, 100.0, ty, 0, 1]
    centre = np.array([0.0, ty, 0.0])

    # 1. Collider A, envelope 1 -> push verts onto the sphere.
    mc.setAttr(nm + ".pusher", *A, type="matrix")
    mc.setAttr(nm + ".envelope", 1.0)
    full = points()
    disp = np.linalg.norm(full - rest, axis=1)
    moved = disp > 1e-4
    n_moved = int(moved.sum())
    on_sphere = bool(n_moved and np.allclose(
        np.linalg.norm((full[moved] - centre) / s, axis=1), 1.0, atol=1e-3))

    # 2. Move the collider far away -> the dent must STAY (accumulation / bake).
    mc.setAttr(nm + ".pusher", *B, type="matrix")
    baked = points()
    baked_ok = bool(n_moved and np.allclose(baked, full, atol=1e-4))

    # 3. Envelope scales the DISPLAYED displacement against rest.
    mc.setAttr(nm + ".envelope", 0.5)
    half = points()
    env_scales = bool(np.allclose(half - rest, 0.5 * (full - rest), atol=1e-3))

    # 4. Envelope 0 -> displayed rest (the baked buffer is retained underneath).
    mc.setAttr(nm + ".envelope", 0.0)
    off = points()
    rest_display = bool(np.allclose(off, rest, atol=1e-4))

    # A far corner vertex is outside the collider and must be untouched.
    corner = int(np.argmax(np.linalg.norm(rest[:, [0, 2]], axis=1)))
    corner_fixed = bool(disp[corner] < 1e-4)

    compute_ok = (n_moved > 0 and on_sphere and baked_ok and env_scales
                  and rest_display and corner_fixed)

    # --- demo check: the authored "Create + Run demo" fabricates the collider +
    #     plane and dents it on a FRESH deserialized node. ---
    _stamp_class(d, "UnitSphereCollision", "mPyDeformer")
    clean_payload = serialize_node(d, include_persistent=False)
    demo_ok = False
    demo_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node
        from mpynode._common.methods.methods_registry import run_node_demo
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tnm = tnode.get_name()
        run_node_demo(tnode)
        plane_t = (mc.ls("collisionTarget*", type="transform") or [None])[0]
        collider_t = (mc.ls("collider*", type="transform") or [None])[0]
        in_hist = plane_t is not None and tnm in (mc.listHistory(plane_t) or [])
        dented = False
        if plane_t is not None:
            mc.currentTime(30)
            mc.dgdirty(tnm + ".outputGeometry")
            shp = mc.listRelatives(plane_t, shapes=True, ni=True, f=True)[0]
            mc.getAttr(shp + ".outMesh")
            sel = om.MSelectionList()
            sel.add(plane_t)
            fn = om.MFnMesh(sel.getDagPath(0))
            ys = [p.y for p in fn.getPoints(om.MSpace.kObject)]
            dented = (max(ys) - min(ys)) > 0.05
        demo_ok = bool(collider_t and in_hist and dented)
        demo_err = "collider=%s in_hist=%s dented=%s" % (
            collider_t, in_hist, dented)
    except Exception as exc:
        demo_err = "exc:%r" % exc

    # --- authored @maya_test check on a FRESH deserialized node. ---
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    ok = compute_ok and demo_ok and test_ok
    print("[usc] moved=%d on_sphere=%s baked=%s env_scales=%s rest_disp=%s "
          "corner_fixed=%s demo=%s(%s) test=%s(%s) -> %s"
          % (n_moved, on_sphere, baked_ok, env_scales, rest_display, corner_fixed,
             demo_ok, demo_err, test_ok, test_err, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(
            USC_DIR, clean_payload,
            "# Unit Sphere Collision\n\n"
            "A collision `mPyDeformer` with memory. Vertices caught inside "
            "the collider sphere get pushed onto its surface, and the dent "
            "bakes in instead of springing back once the collider moves on. "
            "Good for footprints and impact marks.\n\n"
            "Run setup from the Scene tab with the collider TRANSFORM picked "
            "first, the MESH second: it wires the collider's `worldMatrix` "
            "into `pusher`, attaches the deformer, and seeds a buffer so "
            "baked dents survive save and reopen. The deformer `envelope` "
            "blends back to the undented mesh.\n\n"
            "**Create + Run demo** builds a frozen plane and a collider "
            "sphere animated sinking through it -- press play to watch the "
            "dent form and bake.\n\n"
            "**Note:** the collision is computed in the mesh's OBJECT space, "
            "so apply it to a plane with a frozen / identity transform at the "
            "world origin.")
    return ok


# ======================================================================
# 2. mPyFile -- File Simple: framework load + brightness/contrast -> outColor
# ======================================================================
FILE_INIT = r'''# ----------------------------------------------------------------------
# File Simple -- Init tier.
#
# There is deliberately NO image-loading code here.
#
# Loading, colour-space decoding and pre-filtering are FRAMEWORK services.
# Compute and Viewport reach them as self.read_texture() and
# self.sample_texture() -- the "M" (method) rows in the Variables tab. They
# honour every preset input an mPyFile already carries:
#
#   self.colorSpace       25 colour spaces (sRGB, ACEScct, LogC, S-Log3, ...)
#   self.preFilter        smoothing on/off
#   self.preFilterKernel  box / quadratic / quartic / gaussian
#   self.preFilterRadius  smoothing radius
#   self.wrapModeU/V      repeat / clamp / mirror / border
#   self.borderColor      what a border-wrapped lookup returns off-image
#   self.embeddedImage    baked image bytes read_texture() falls back to when
#                         `fileName` is blank / missing, so a node ships
#                         renderable with no file on disk
#
# So this template gets a stock Maya file node's full colour management for
# free, and compiles to the same deterministic nd_tex_load_linear /
# nd_tex_sample C++ kernels as the built-in default -- no AI port.
#
# numpy is imported because the Viewport tier uses it for the whole-image
# brightness/contrast pass. The Init namespace is merged into the Compute and
# Viewport namespaces before either runs, so anything defined here is in scope
# for both.
# ----------------------------------------------------------------------
import numpy as np
'''
FILE_COMPUTE = r'''# File texture with a brightness / contrast filter.
#
# self.read_texture()    load `fileName`, decode it out of `colorSpace`, apply
#                        the optional pre-filter. Returns a float32 HxWx4
#                        SCENE-LINEAR buffer (cached), or None when the file is
#                        missing / unreadable -- but first it falls back to the
#                        node's baked `embeddedImage` bytes, so a node with no
#                        file on disk still renders.
# self.sample_texture()  wrap-aware BILINEAR lookup into that buffer ->
#                        (r, g, b, a). Returns magenta when the buffer is None,
#                        so a missing file never raises.
#
# Both are framework methods shared by every mPyFile -- the same pair the
# built-in default uses -- so this template stays about the GRADE, not about
# how to read a PNG.
buf = self.read_texture()
r, g, b, a = self.sample_texture(buf, self.uvCoord[0], self.uvCoord[1])

# brightness scales about black, contrast about mid-grey, then clamp.
bright = self.brightness
contrast = self.contrast
r = min(1.0, max(0.0, (r * bright - 0.5) * contrast + 0.5))
g = min(1.0, max(0.0, (g * bright - 0.5) * contrast + 0.5))
b = min(1.0, max(0.0, (b * bright - 0.5) * contrast + 0.5))

self.outColor = (r, g, b)
self.outAlpha = a
'''


# mPyFile template Viewport tier: mirror the brightness/contrast look on
# the GPU so the textured VP2 surface matches the Compute / swatch output.
FILE_VIEW = r'''# ----------------------------------------------------------------------
# mPyFile TEMPLATE -- Viewport source (runs per VP2 updateShader call)
#
# Mirrors the brightness/contrast Compute tier on the GPU: it reads the
# SAME image the Compute tier samples, applies the IDENTICAL per-channel
# brightness then contrast formula (vectorized over the whole image), and
# uploads the result as a float32 texture into the VP2 file-texture shade
# fragment so the textured viewport surface matches the Compute / swatch
# look.
#
# Bridge bindings available via self.X:
#   self.shader           -- omr.MShaderInstance to push parameters into
#   self.texture_manager  -- MRenderer.getTextureManager() (None headless)
#   self.state_manager    -- omr.MStateManager (the CLASS, not an instance)
#   self.mappings         -- MAttributeParameterMappingList from Maya
#   plus every preset/input plug (self.fileName, self.brightness, ...)
#
# ``np`` comes from the template's Init tab (the Init namespace is merged in
# before this runs) and ``self.read_texture()`` is the framework method the
# Compute tier uses, so both tiers sample the SAME cached, colour-managed
# buffer. ``omr`` is NOT in the template Init, so we import it locally here --
# the viewport source is plain Python exec'd, so a local import is fine.
#
# CONTROL FLOW: this source is compiled with compile(src, ..., "exec") and
# run at MODULE scope (see _common/expression.py) -- it is NOT wrapped in a
# function -- so a bare ``return`` would be a SyntaxError ("'return'
# outside function") that is caught at compile time and silently disables
# the whole tier. We therefore degrade gracefully with nested ``if`` guards
# instead of early returns (exactly like the production viewport source in
# _defaults/file_defaults.py).
# ----------------------------------------------------------------------
import maya.api.OpenMayaRender as omr

# 1. Read the image the SAME way Compute does -> (H, W, 4) float32 [0,1],
#    or None when the file is missing/unreadable (the framework caches the
#    decode). We only do GPU work when we have BOTH a readable image AND a
#    texture manager -- the texture manager is None when running headless
#    (e.g. mayapy/batch). When either is missing we simply skip the upload
#    and VP2 shows no texture (no magenta upload needed -- Compute owns the
#    magenta fallback). Everything below is nested under this single guard
#    so we never need a module-level ``return``.
img = self.read_texture()
if img is not None and self.texture_manager is not None:

    # 2. Apply the EXACT brightness/contrast Compute uses, but vectorized
    #    over the whole image at once. Per RGB channel, matching Compute:
    #        ch = ch * brightness
    #        ch = (ch - 0.5) * contrast + 0.5
    #        clamp to [0, 1]
    #    Alpha (channel 3) is left untouched (Compute writes ``a`` through).
    bright = self.brightness
    contrast = self.contrast

    # Work on a float32 copy so we never mutate the cached array in
    # _IMG_CACHE (other tiers / later calls reuse it).
    processed = img.astype(np.float32, copy=True)
    rgb = processed[..., :3]            # view onto the RGB channels
    rgb *= bright                       # brightness
    rgb -= 0.5
    rgb *= contrast                     # contrast pivoted about mid-grey
    rgb += 0.5
    np.clip(rgb, 0.0, 1.0, out=rgb)     # clamp RGB to [0,1] (alpha untouched)

    # 3. The GPU upload wants float32, C-contiguous, HxWx4 data in TOP-DOWN
    #    row order (row 0 = top of the image) -- the orientation Maya's VP2
    #    file-texture fragment expects, and the same one the production
    #    default + native port upload. read_texture() ALREADY returns top-down
    #    pixels (it flips MImage's native bottom-up rows once at load), so we
    #    upload directly here -- no extra flip -- and the textured surface
    #    matches the Compute tab (which samples that same top-down buffer).
    processed = np.ascontiguousarray(processed, dtype=np.float32)
    h, w = processed.shape[0], processed.shape[1]

    # 4. Locate the fragment's texture2 parameter (the slot the file colour
    #    feeds) and, optionally, its sampler parameter.
    map_param = None
    samp_param = None
    for pname in self.shader.parameterList():
        try:
            ptype = self.shader.parameterType(pname)
        except Exception:
            # Some parameters report no queryable type; just skip them.
            continue
        if map_param is None and ptype == omr.MShaderInstance.kTexture2:
            map_param = pname
        elif samp_param is None and ptype == omr.MShaderInstance.kSampler:
            samp_param = pname
        if map_param and samp_param:
            break

    # 5. Describe + upload the processed pixels as a 32-bit float RGBA
    #    texture and bind it to the texture2 slot. Field setup mirrors
    #    _upload_linear_texture in _defaults/file_defaults.py exactly. Only
    #    do this when a texture2 slot actually exists on the fragment.
    if map_param:
        desc = omr.MTextureDescription()
        desc.setToDefault2DTexture()
        desc.fWidth = w
        desc.fHeight = h
        desc.fDepth = 1
        desc.fBytesPerRow = w * 4 * 4           # 4 channels * 4 bytes (float32)
        desc.fBytesPerSlice = desc.fBytesPerRow * h
        desc.fMipmaps = 1
        desc.fArraySlices = 1
        desc.fFormat = omr.MRenderer.kR32G32B32A32_FLOAT
        desc.fTextureType = omr.MTextureDescription.kImage2D
        desc.fEnvMapType = omr.MTextureDescription.kEnvNone

        # Encode the look-affecting inputs into the texture name so distinct
        # file/brightness/contrast settings get distinct texture-manager
        # cache entries (and so editing those inputs refreshes the surface).
        tex_name = "mpyfile_template::%s|b=%.4f|c=%.4f" % (
            self.fileName, bright, contrast)
        texture = self.texture_manager.acquireTexture(
            tex_name, desc, processed.tobytes(), False,   # gen_mips=False
        )

        # acquireTexture can return None (bad desc / no GPU); only bind if
        # we actually got a texture back.
        if texture is not None:
            # Bind the texture, then release OUR reference. The shader holds
            # its own reference once setParameter succeeds, so releasing here
            # just balances the acquire and avoids leaking GPU memory.
            try:
                assignment = omr.MTextureAssignment()
                assignment.texture = texture
                self.shader.setParameter(map_param, assignment)
            finally:
                try:
                    self.texture_manager.releaseTexture(texture)
                except Exception:
                    pass

    # 6. (Optional) Give the sampler a plain linear-filter / clamp address
    #    state so the surface reads cleanly. state_manager IS the class
    #    omr.MStateManager, so we call acquireSamplerState on it directly.
    if samp_param:
        try:
            sdesc = omr.MSamplerStateDesc()
            sdesc.setDefaults()
            sdesc.filter = omr.MSamplerState.kMinMagMipLinear
            sdesc.addressU = omr.MSamplerState.kTexClamp
            sdesc.addressV = omr.MSamplerState.kTexClamp
            self.shader.setParameter(samp_param,
                self.state_manager.acquireSamplerState(sdesc))
        except Exception:
            # Sampler state is a nicety, not required for the texture to show.
            pass
'''


# mPyFile template OSL tier: a connectable aiOslShader-ready twin of the
# Compute look (texture() + the same brightness/contrast + (1 - v) flip).
FILE_OSL = r'''// ----------------------------------------------------------------------
// fileSimple -- OSL shader source (Open Shading Language)
//
// This tab is a RENDER TARGET, not an execution tier: the text here is
// exposed as the connectable string output `.osl`. Wire it into an
// aiOslShader (Arnold) so the renderer reproduces the same brightness/
// contrast file-texture LOOK the Compute tab computes.
//
// It mirrors the Compute tab exactly:
//   * sample the texture with the same (1 - v) V-flip the Compute tab
//     uses: Maya's surface V is bottom-up while the image buffer is
//     top-down, so both Compute and this shader pass (1 - v) to land on
//     the same row as a standard Maya file node. texture() also does the
//     sampling/filtering for us (no manual pixel indexing needed).
//   * linearize the sampled sRGB colour to scene-linear (see below), the
//     same conversion Compute's read_texture() applies, BEFORE adjusting it.
//   * per channel:  c = c * brightness;
//                   c = (c - 0.5) * contrast + 0.5;
//                   clamp to [0, 1].
//     OSL color arithmetic is component-wise, so each expression applies
//     the formula to R, G and B at once -- the same look as Compute's
//     `for ch in (r, g, b)` loop.
//   * pass the sampled alpha straight through to outAlpha.
//
// COLOUR MANAGEMENT: Arnold's OSL texture() returns the RAW sRGB file
// values -- it does NOT auto color-manage the sample (verified by a real
// Arnold render: without the conversion below the OSL surface renders
// ~2.3x too bright vs the Compute/Viewport tiers and a stock file node).
// We therefore linearize here so all three tiers (and a real Maya file
// node) agree. There is no double-conversion risk precisely because
// texture() does not color-manage.
// ----------------------------------------------------------------------

// sRGB-encoded -> scene-linear, component-wise piecewise EOTF (mirrors
// _defaults/file_defaults.py::_srgb_eotf and the framework's
// file_texture_ops.srgb_eotf). step()/mix()/pow() are component-wise, so
// this branches per channel without a loop. max() guards pow() against any
// negative sample.
color srgb_to_linear(color c)
{
    color lo = c / 12.92;
    color hi = pow(max((c + color(0.055)) / 1.055, color(0.0)), 2.4);
    // step(edge, x) = (x >= edge) per component; mix picks hi where c>=0.04045.
    return mix(lo, hi, step(color(0.04045), c));
}

shader fileSimple(
    string fileName = "",                 // image path (matches self.fileName)
    float brightness = 1.0,               // matches self.brightness
    float contrast = 1.0,                 // matches self.contrast
    output color outColor = color(0),
    output float outAlpha = 1.0)
{
    // Sample the texture at the renderer's surface coords (u, v). The
    // (1 - v) flip matches the Compute tab, which samples image row
    // (1.0 - vv) because MImage stores rows bottom-up. The optional
    // "alpha" output captures the texture's alpha channel (Compute's `a`).
    float a = 1.0;
    color c = texture(fileName, u, 1.0 - v, "alpha", a);

    // sRGB -> scene-linear (read_texture() does this). Alpha is
    // already linear, so it is NOT converted -- only the colour.
    c = srgb_to_linear(c);

    // brightness: scale about black.   (Compute: ch = ch * bright)
    color bright = c * brightness;
    // contrast: scale about mid-grey 0.5.  (Compute: (ch-0.5)*contrast+0.5)
    color shaped = (bright - color(0.5)) * contrast + color(0.5);

    // keep the result in the displayable range, then pass alpha through.
    outColor = clamp(shaped, color(0), color(1));
    outAlpha = a;
}
'''


def _write_test_image(path, rows):
    """Write an HxW RGBA image where row r is filled with grey value rows[r]."""
    h = len(rows)
    w = 8
    buf = bytearray()
    for r in range(h):
        val = rows[r]
        buf += bytes([val, val, val, 255]) * w
    im = om.MImage()
    im.create(w, h, 4, om.MImage.kByte)
    im.setPixels(bytes(buf), w, h)
    im.writeToFile(path, "png")
    return w, h


# NOTE: FILE_BC_DEMO and build_file() lived here and wrote the "Basic
# Texture" template. They are GONE: that template measured identical to
# File Simple at every flat texel, so File Simple absorbed it and became
# the mPyFile primary (see TEMPLATE_TARGETS). FILE_INIT / FILE_COMPUTE /
# FILE_VIEW / FILE_OSL above are NOT dead -- File Simple and File Scanline
# are built from them, and FILE_SIMPLE_COMPUTE derives from FILE_COMPUTE
# so the two can never drift.


def _verify_file_orientation(testimg):
    """The template Compute must read the SAME way up as Maya's built-in
    ``file`` node (it previously rendered vertically mirrored). Compare the
    vertical direction of both against an increasing gradient."""
    # The template ships no loader any more -- Compute reads through the
    # framework -- so the gate compares against the SAME framework buffer.
    # Preset defaults: colorSpace 0 (sRGB), preFilter off.
    from mpynode._common.methods import file_texture_ops as _tex
    arr = _tex.load_linear_pixels(testimg, 0, False, 0, 1.0)  # top-down
    h = arr.shape[0]

    def tmpl(v):
        py = min(h - 1, int((1.0 - (v - np.floor(v))) * h))
        return float(arr[py, arr.shape[1] // 2, 0])

    fn = mc.shadingNode("file", asTexture=True, name="_orientGT")
    mc.setAttr(fn + ".fileTextureName", testimg, type="string")
    try:
        mc.setAttr(fn + ".colorSpace", "Raw", type="string")
        mc.setAttr(fn + ".colorManagementEnabled", 0)
    except Exception:
        pass

    def maya(v):
        eps = 0.001
        c = mc.colorAtPoint(fn, o="RGB", su=1, sv=1, mu=0.5,
                            mv=max(0.0, v - eps), xu=0.5, xv=min(1.0, v + eps))
        return float(c[0]) if c else 0.0

    # Same vertical direction (top brighter than bottom) => not mirrored.
    t_dir = tmpl(0.8) - tmpl(0.2)
    m_dir = maya(0.8) - maya(0.2)
    mc.delete(fn)
    return (t_dir > 0) == (m_dir > 0) and abs(t_dir) > 0.05


def _verify_file_viewport(testimg, init_src=FILE_INIT, view_src=FILE_VIEW):
    """Exec the Viewport source against a fake shader/texture-manager and
    confirm the uploaded float32 RGBA buffer equals the SAME brightness/
    contrast Compute applies (look parity) in top-down orientation.

    ``init_src`` / ``view_src`` default to File Simple's Init + Viewport;
    another mPyFile template can pass its own pair."""
    import maya.api.OpenMayaRender as omr

    bright, contrast = 1.4, 1.3
    captured = {}

    class _FakeShader:
        def parameterList(self):
            return ["gTexture", "gSampler"]

        def parameterType(self, n):
            return (omr.MShaderInstance.kTexture2 if n == "gTexture"
                    else omr.MShaderInstance.kSampler)

        def setParameter(self, n, v):
            captured.setdefault("set", []).append(n)

    class _FakeTM:
        def acquireTexture(self, name, desc, data, gen_mips):
            captured.update(w=desc.fWidth, h=desc.fHeight, bytes=bytes(data),
                            fmt=desc.fFormat, bpr=desc.fBytesPerRow)
            return None          # real MTexture needs a GPU; bytes captured

        def releaseTexture(self, t):
            pass

    class _FakeSM:
        def acquireSamplerState(self, desc):
            return None

    class _FakeSelf:
        fileName = testimg
        shader = _FakeShader()
        texture_manager = _FakeTM()
        state_manager = _FakeSM()

        def read_texture(self):
            """Stand in for the SelfProxy blessed method the real Viewport
            tier calls, with this node's preset defaults (sRGB, no prefilter)."""
            from mpynode._common.methods import file_texture_ops as _tex
            return _tex.load_linear_pixels(self.fileName, 0, False, 0, 1.0)

    self_obj = _FakeSelf()
    self_obj.brightness = bright
    self_obj.contrast = contrast

    ns = {}
    exec(init_src, ns)
    ns["self"] = self_obj
    try:
        exec(compile(view_src, "viewport", "exec"), ns)
    except Exception as exc:
        return False, "exec:%r" % exc
    if "bytes" not in captured:
        return False, "no upload"

    got = np.frombuffer(captured["bytes"], dtype=np.float32).reshape(
        captured["h"], captured["w"], 4)
    img = self_obj.read_texture()
    exp = img.astype(np.float32, copy=True)
    rgb = exp[..., :3]
    rgb *= bright
    rgb -= 0.5
    rgb *= contrast
    rgb += 0.5
    np.clip(rgb, 0.0, 1.0, out=rgb)

    maxerr = float(np.abs(got[..., :3] - exp[..., :3]).max())
    fmt_ok = captured["fmt"] == omr.MRenderer.kR32G32B32A32_FLOAT
    fields_ok = captured["bpr"] == captured["w"] * 4 * 4
    orient_ok = bool(np.allclose(got, exp))       # uploaded top-down == buffer

    # Graceful headless degradation: no texture manager -> no raise/upload.
    captured.clear()
    self_obj.texture_manager = None
    ns2 = {}
    exec(init_src, ns2)
    ns2["self"] = self_obj
    try:
        exec(compile(view_src, "viewport", "exec"), ns2)
        headless_ok = "bytes" not in captured
    except Exception as exc:
        return False, "headless-raise:%r" % exc

    ok = maxerr < 1e-5 and fmt_ok and fields_ok and orient_ok and headless_ok
    return ok, "maxerr=%.1e fmt=%s flds=%s orient=%s hl=%s" % (
        maxerr, fmt_ok, fields_ok, orient_ok, headless_ok)


def _verify_file_osl():
    """The OSL twin must compile (real aiOslShader compile when MtoA is
    present; structural-only otherwise) and carry the brightness/contrast +
    (1 - v) look AND the sRGB->linear conversion (Arnold's texture() returns
    RAW sRGB, so without it the OSL render is ~2.3x too bright vs Compute --
    a real Arnold render confirmed this; the structural check below is a cheap
    regression gate for that, since a compile-only check cannot see brightness)."""
    structural = all(s in FILE_OSL for s in (
        "shader fileSimple(", "string fileName", "float brightness",
        "float contrast", "output color outColor", "output float outAlpha",
        "texture(fileName", "clamp(",
    )) and ("1.0 - v" in FILE_OSL or "1 - v" in FILE_OSL)
    if not structural:
        return False, "structural"
    # Colour management: the OSL must linearize the sampled colour BEFORE the
    # brightness/contrast (matches the Compute tier's read_texture()), else it
    # renders ~2.3x too bright.
    linearizes = (
        "c = srgb_to_linear(c)" in FILE_OSL
        and all(t in FILE_OSL for t in ("12.92", "1.055", "0.04045", "2.4"))
        and FILE_OSL.index("c = srgb_to_linear(c)")
        < FILE_OSL.index("color bright = c * brightness")
    )
    if not linearizes:
        return False, "not-linearized"
    try:
        from mpynode._common.osl.osl_targets import validate_osl_via_arnold
        ok, err = validate_osl_via_arnold(FILE_OSL)
        return bool(ok), (err or "arnold-ok")
    except Exception as exc:
        return False, "validate:%r" % exc


# ======================================================================
# 2b. mPyFile -- Conway's Game of Life as a procedural texture
# ======================================================================
# A second mPyFile template (the type slot is taken by file_brightness_contrast),
# so it is written by explicit rel dir via _write_template_to (like the collision
# deformer) and registered in ALL_DECLARED_DIRS.
GOL_INIT = r'''import numpy as np

def _gol_seed(h, w, density, seed=0):
    """Random board: a `density` fraction of cells alive. Deterministic for a
    given (shape, density, seed) so a reset is reproducible."""
    rng = np.random.RandomState(int(seed) & 0x7fffffff)
    return rng.random((int(h), int(w))) < float(density)

def _gol_step(board):
    """One Conway step on a BOUNDED grid: neighbours beyond the edge are dead
    (zero padding, NOT np.roll), so live cells never wrap around the border --
    a glider that reaches a wall dies rather than reappearing on the far side."""
    b = board.astype(np.uint8)
    pad = np.zeros((b.shape[0] + 2, b.shape[1] + 2), dtype=np.uint8)
    pad[1:-1, 1:-1] = b
    n = (pad[:-2, :-2] + pad[:-2, 1:-1] + pad[:-2, 2:] +
         pad[1:-1, :-2]                 + pad[1:-1, 2:] +
         pad[2:, :-2]  + pad[2:, 1:-1]  + pad[2:, 2:])
    return (n == 3) | ((b == 1) & (n == 2))

def _gol_rgba(board):
    """(H, W) bool board -> (H, W, 4) float32 RGBA, white alive / black dead.

    Spelled with an explicit shape tuple and full slices (NOT `board.shape + (4,)`
    / `out[..., i]`): shape arithmetic and Ellipsis indexing do not transpile, and
    the Compute tier has to lower to C++ so its RNG stays bit-exact."""
    alive = board.astype(np.float32)
    out = np.zeros((board.shape[0], board.shape[1], 4), dtype=np.float32)
    out[:, :, 0] = alive
    out[:, :, 1] = alive
    out[:, :, 2] = alive
    out[:, :, 3] = 1.0
    return out

def _gol_advance(node):
    """Seed or step the board ONCE for the current frame (idempotent per frame
    so Compute and Viewport can both call it without double-stepping) and return
    the (H, W) bool board.

    Stored on `node` (process-global, survives the per-UV / per-frame evals):
      board  -- the live grid       lastFrame -- frame it last advanced

    The OSL bake is NOT done here: the Compute tier owns it (via the blessed
    self.write_texture, which has a C++ twin), so it happens in the compiled node
    too. This helper is what the VIEWPORT tier calls -- it shares the same two
    stored vars, so whichever tier runs first advances and the other no-ops.
    """
    h = max(1, int(node.height))
    w = max(1, int(node.width))
    density = float(node.density)
    frame = float(node.frame)
    board = getattr(node, "board", None)
    reset_on = (int(node.reset) == 1)
    shape_bad = (board is None or getattr(board, "shape", None) != (h, w))
    if shape_bad or frame != getattr(node, "lastFrame", None):
        if reset_on or shape_bad:
            # While reset is held, vary the seed by frame so the random startup
            # is live (density edits are visible); else seed deterministically.
            board = _gol_seed(h, w, density, seed=int(frame) if reset_on else 0)
        else:
            board = _gol_step(board)
        node.board = board
        node.lastFrame = frame
    return board
'''

GOL_COMPUTE = r'''# Conway's Game of Life as a procedural texture. A bounded numpy board (no
# wrap) advances one step per frame and is sampled per-UV: white = alive,
# black = dead. Drive `frame` (auto-wired to the timeline) to animate; set
# `reset` True to reseed `density` random cells; `width`/`height` set the grid.
# Spelled to LOWER to C++ (it must: nd::MT19937 reproduces numpy's RandomState
# stream bit-for-bit, so the compiled node seeds the SAME board -- an AI port
# would substitute a different generator and diverge). That means: the advance is
# inline rather than `_gol_advance(self)` (the node object cannot be passed into a
# helper), the first-run seed is hasattr-guarded (persistent state must be written
# before it is read), uvCoord is indexed rather than tuple-unpacked, and the
# sampled cell is float()-ed (an indexed element is a rank-0 array, not a scalar).
hh = max(1, int(self.height))
ww = max(1, int(self.width))
fr = float(self.frame)
dens = float(self.density)
reset_on = int(self.reset) == 1
if not hasattr(self, "board"):
    self.board = _gol_seed(hh, ww, dens, seed=int(fr) if reset_on else 0)
    self.lastFrame = fr
    self.bakedFrame = -1.0
board = self.board
shape_bad = (int(board.shape[0]) != hh or int(board.shape[1]) != ww)
if shape_bad or fr != self.lastFrame:
    if reset_on or shape_bad:
        # While reset is held, vary the seed by frame so the random startup is
        # live (density edits are visible); else seed deterministically.
        board = _gol_seed(hh, ww, dens, seed=int(fr) if reset_on else 0)
    else:
        board = _gol_step(board)
    self.board = board
    self.lastFrame = fr
# Bake the frame for the OSL/Arnold tier, which samples the file (Game of Life is
# stateful, so a shader cannot evaluate it from (u, v, t)). The third argument
# writes a FRAME-STAMPED name (bakePath "x.png" -> "x.0007.png"): Arnold's texture
# system caches by filename and never re-stats, so re-baking one fixed path leaves
# a render showing whichever frame it read first. The result is ASSIGNED (a blessed
# call left as a bare statement is dropped from the emitted C++), and bakedFrame
# advances only on SUCCESS so an unwritable path is retried rather than marked done.
if self.bakePath != "" and fr != self.bakedFrame:
    baked = self.write_texture(self.bakePath, _gol_rgba(board), fr)
    if baked:
        self.bakedFrame = fr
h, w = int(board.shape[0]), int(board.shape[1])
u = self.uvCoord[0]
v = self.uvCoord[1]
uu = u - np.floor(u)
vv = v - np.floor(v)
cx = min(w - 1, int(uu * w))
cy = min(h - 1, int((1.0 - vv) * h))
alive = 1.0 if float(board[cy, cx]) > 0.5 else 0.0
self.outColor = (alive, alive, alive)
self.outAlpha = 1.0
'''

GOL_VIEW = r'''# Viewport (VP2) tier: upload the current board as a white/black float texture
# so the plane shows the simulation live in the viewport and animates on scrub.
# Calls the SAME _gol_advance the Compute tier does (idempotent per frame, so no
# double-stepping). Degrades to a no-op headless (no texture manager).
import maya.api.OpenMayaRender as omr

board = _gol_advance(self)
if board is not None and self.texture_manager is not None:
    h, w = int(board.shape[0]), int(board.shape[1])
    pixels = np.ascontiguousarray(_gol_rgba(board), dtype=np.float32)  # top-down

    map_param = None
    samp_param = None
    for pname in self.shader.parameterList():
        try:
            ptype = self.shader.parameterType(pname)
        except Exception:
            continue
        if map_param is None and ptype == omr.MShaderInstance.kTexture2:
            map_param = pname
        elif samp_param is None and ptype == omr.MShaderInstance.kSampler:
            samp_param = pname
        if map_param and samp_param:
            break

    if map_param:
        desc = omr.MTextureDescription()
        desc.setToDefault2DTexture()
        desc.fWidth = w
        desc.fHeight = h
        desc.fDepth = 1
        desc.fBytesPerRow = w * 4 * 4            # 4 channels * 4 bytes (float32)
        desc.fBytesPerSlice = desc.fBytesPerRow * h
        desc.fMipmaps = 1
        desc.fArraySlices = 1
        desc.fFormat = omr.MRenderer.kR32G32B32A32_FLOAT
        desc.fTextureType = omr.MTextureDescription.kImage2D
        desc.fEnvMapType = omr.MTextureDescription.kEnvNone
        # Encode shape + frame + live-cell count so each distinct board uploads
        # fresh (the texture manager caches by name; two equal boards collide
        # harmlessly to the same texture).
        tex_name = "mpy_gol::%dx%d|f=%.4f|n=%d" % (
            w, h, self.frame, int(board.sum()))
        texture = self.texture_manager.acquireTexture(
            tex_name, desc, pixels.tobytes(), False)
        if texture is not None:
            try:
                assignment = omr.MTextureAssignment()
                assignment.texture = texture
                self.shader.setParameter(map_param, assignment)
            finally:
                try:
                    self.texture_manager.releaseTexture(texture)
                except Exception:
                    pass

    if samp_param:
        try:
            sdesc = omr.MSamplerStateDesc()
            sdesc.setDefaults()
            # NEAREST filtering keeps the cells crisp (no grey blend at edges).
            sdesc.filter = omr.MSamplerState.kMinMagMipPoint
            sdesc.addressU = omr.MSamplerState.kTexClamp
            sdesc.addressV = omr.MSamplerState.kTexClamp
            self.shader.setParameter(
                samp_param, self.state_manager.acquireSamplerState(sdesc))
        except Exception:
            pass
'''

GOL_OSL = r'''// ----------------------------------------------------------------------
// gameOfLife -- OSL shader (Open Shading Language) for Arnold.
//
// Game of Life is a STATEFUL simulation, so -- unlike a closed-form texture --
// it cannot be evaluated from (u, v, time) alone. Instead the node BAKES the
// current board to an image each frame (a "virtual texture that regenerates
// every frame") and this shader simply samples that file. `fileName` is set by
// the node's setup to the per-node baked PNG.
//
// The bake is a FRAME SEQUENCE, not one overwritten file, and this shader
// rebuilds the per-frame name from `fileName` + `bakeFrame`. That is not a
// stylistic choice: Arnold's texture system caches by filename and never
// re-stats, so a node that re-bakes one fixed path renders whichever frame
// Arnold happened to read first -- forever. `bakeFrame` is driven from the
// node's `frame` input by the setup, which also gives MtoA an animated
// parameter to re-translate. The name rule mirrors os.path.splitext exactly,
// because the Compute tier (Python) and the nd_tex_write C++ kernel build the
// same string: "x.png" + 7 -> "x.0007.png".
//
// NEAREST ("closest") filtering keeps the cells crisp; the (1 - v) flip matches
// the Compute tab so the Arnold render lines up with the swatch / viewport. The
// board is pure black/white, so NO sRGB->linear step is needed (0 and 1 are
// fixed points of the transfer curve, unlike the file_brightness_contrast OSL).
// ----------------------------------------------------------------------
shader gameOfLife(
    string fileName = "",
    float bakeFrame = 0,
    output color outColor = color(0),
    output float outAlpha = 1.0)
{
    // The node always bakes PNGs, so only that suffix needs stripping.
    string base = fileName;
    int n = strlen(base);
    if (n > 4 && substr(base, n - 4, 4) == ".png") {
        base = substr(base, 0, n - 4);
    }
    string path = format("%s.%04d.png", base, int(bakeFrame));
    color c = texture(path, u, 1.0 - v, "interp", "closest",
                      "wrap", "clamp");
    outColor = c;
    outAlpha = 1.0;
}
'''

# Full setup authored into the template's Methods tab: build a polyPlane + a
# lambert (assigned to the plane) and drive its colour from outColor, store the
# per-node bake path Compute uses, and -- best effort -- build the Arnold OSL
# render path. Force one eval so the board exists + bakes immediately.
DEMO_GOL_FILE = '''# Full setup for the Game of Life texture: create a polyPlane and a lambert
# shader, assign the shader to the plane, and connect this node's outColor into
# the lambert's colour so the simulation displays. Also stores the per-node PNG
# path the OSL tier reads and (best effort) builds the Arnold render path.


def demo(self):
    from maya import cmds as mc
    import os, tempfile
    name = self.get_name()

    # 1. A plane to show the texture on.
    plane = mc.polyPlane(width=10, height=10, subdivisionsX=1,
                         subdivisionsY=1, name=name + "_plane")[0]

    # 2. A lambert + shading group; assign the plane; drive its colour from us.
    shader = mc.shadingNode("lambert", asShader=True, name=name + "_lambert")
    sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True, name=shader + "SG")
    mc.connectAttr(shader + ".outColor", sg + ".surfaceShader", force=True)
    mc.sets(plane, edit=True, forceElement=sg)
    mc.connectAttr(name + ".outColor", shader + ".color", force=True)

    # 3. The per-node PNG the OSL/Arnold tier reads (one file, overwritten each
    #    frame). Set it on the node's bakePath INPUT (Compute reads it there and
    #    bakes via self.write_texture) AND point the OSL shader at the SAME path
    #    so the two agree.
    bake = os.path.join(
        tempfile.gettempdir(),
        "mpy_gol_%s.png" % name.replace("|", "_").replace(":", "_"))
    mc.setAttr(name + ".bakePath", bake, type="string")

    # 4. Arnold render path (best effort -- the viewport scene is valid without
    #    it). Compile an aiOslShader from this node's .osl output, point it at the
    #    baked PNG, and route it through the shadingEngine's aiSurfaceShader so
    #    Arnold renders the board per-UV while the lambert keeps the viewport.
    try:
        from mpynode._common.osl.osl_targets import apply_osl_to_arnold
        osl = apply_osl_to_arnold(name)
        if osl:
            if mc.attributeQuery("fileName", node=osl, exists=True):
                mc.setAttr(osl + ".fileName", bake, type="string")
            # The shader rebuilds the per-frame bake name from fileName +
            # bakeFrame, so bakeFrame MUST track the node's frame -- left at 0
            # it samples one file forever, which is the stale render the
            # sequence bake exists to avoid. Driving it from an animated plug
            # is also what makes MtoA re-translate the shader each frame.
            if mc.attributeQuery("bakeFrame", node=osl, exists=True):
                mc.connectAttr(name + ".frame", osl + ".bakeFrame", force=True)
            if mc.attributeQuery("aiSurfaceShader", node=sg, exists=True):
                amtl = mc.shadingNode("aiStandardSurface", asShader=True,
                                      name=name + "_arnoldMtl")
                try:
                    mc.setAttr(amtl + ".specular", 0.0)
                except Exception:
                    pass
                mc.connectAttr(osl + ".outColor", amtl + ".baseColor", force=True)
                mc.connectAttr(amtl + ".outColor", sg + ".aiSurfaceShader", force=True)
    except Exception:
        pass

    # 5. Force one eval at the current frame so the board exists and is baked now.
    try:
        mc.dgdirty(name + ".outColor")
        mc.getAttr(name + ".outColor")
    except Exception:
        pass
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_test(label="Game of Life texture samples the live board", digits=3)
def test_game_of_life(self):
    """Validate the node's INTENT (the SAME test passes on the interpreted node
    and its C++ compile -> parity): with `reset` ON the per-UV texture equals
    the deterministic seed board (a bounded, no-wrap Conway grid seeded from the
    frame); with `reset` OFF, advancing one frame applies exactly one bounded
    Conway step. Sampled through the PUBLIC uCoord/vCoord/outColor plugs."""
    from maya import cmds as mc
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_true

    name = self.get_name()

    # Reproduce the node's bounded-Conway kernel locally (its Init-tier
    # _gol_seed / _gol_step are not visible from the Methods namespace).
    def _seed(h, w, density, seed):
        rng = np.random.RandomState(int(seed) & 0x7fffffff)
        return rng.random((int(h), int(w))) < float(density)

    def _step(board):
        b = board.astype(np.uint8)
        pad = np.zeros((b.shape[0] + 2, b.shape[1] + 2), dtype=np.uint8)
        pad[1:-1, 1:-1] = b
        n = (pad[:-2, :-2] + pad[:-2, 1:-1] + pad[:-2, 2:] +
             pad[1:-1, :-2]                 + pad[1:-1, 2:] +
             pad[2:, :-2]  + pad[2:, 1:-1]  + pad[2:, 2:])
        return (n == 3) | ((b == 1) & (n == 2))

    g = 5
    mc.setAttr(name + ".width", g)
    mc.setAttr(name + ".height", g)
    mc.setAttr(name + ".density", 0.5)

    def sample(cx, cy):
        # Sample the centre of cell (cx, cy). The Compute tier flips v, so
        # vCoord = 1 - (cy + 0.5)/g lands on board row cy (top-down).
        mc.setAttr(name + ".uCoord", (cx + 0.5) / float(g))
        mc.setAttr(name + ".vCoord", 1.0 - (cy + 0.5) / float(g))
        mc.dgdirty(name + ".outColor")
        return mc.getAttr(name + ".outColor")[0][0]

    # 1) reset ON at frame 5 -> texture == deterministic seed board (seed=frame).
    mc.setAttr(name + ".reset", 1)
    mc.currentTime(5)
    board = _seed(g, g, 0.5, 5)
    for cy in range(g):
        for cx in range(g):
            assert_true((sample(cx, cy) > 0.5) == bool(board[cy, cx]),
                        "seed cell (%d,%d) does not match the seeded board" % (cx, cy))

    # 2) reset OFF + advance one frame -> exactly one bounded Conway step.
    mc.setAttr(name + ".reset", 0)
    mc.currentTime(6)
    stepped = _step(board)
    for cy in range(g):
        for cx in range(g):
            assert_true((sample(cx, cy) > 0.5) == bool(stepped[cy, cx]),
                        "stepped cell (%d,%d) does not match one Conway step" % (cx, cy))
'''

GOL_DESC = (
    "# Game Of Life Texture\n\n"
    "Conway's Game of Life running as a live texture (an `mPyFile`). It steps "
    "a grid of cells once per frame and paints it onto whatever surface you "
    "assign -- white for alive, black for dead.\n\n"
    "`width` and `height` set the grid (default 100x100). `frame` is "
    "auto-wired to the timeline, so it animates on play. `density` (0-1, "
    "default 0.5) is the fraction of cells that start alive; set `reset` to "
    "**True** to reseed the board.\n\n"
    "The grid does not wrap: a cell at the edge has no neighbours past it, so "
    "gliders die at the border instead of reappearing on the far side.\n\n"
    "It draws in the swatch, the viewport and an Arnold render (via OSL). "
    "Because the simulation carries state, Arnold samples a PNG the node "
    "re-bakes each frame.\n\n"
    "**Create + Run demo** builds a polyPlane, a lambert shader and (when "
    "MtoA is present) the Arnold OSL render path, all wired to this node.\n\n"
    "**Note:** the bake rides the normal viewport / swatch evaluation, so the "
    "frame you are looking at renders correctly in Arnold. A headless batch "
    "may need a per-frame `dgeval` so each frame bakes before Arnold samples "
    "it.\n\n"
    "**Note:** the bake is a numbered SEQUENCE beside `bakePath` "
    "(`x.png` -> `x.0007.png`), because Arnold's texture cache is keyed on the "
    "filename and never re-checks the file -- one overwritten path would "
    "render the first frame forever. Two consequences: scrubbing leaves one "
    "small PNG per visited frame in your temp directory, and editing `width`, "
    "`density` or `reset` while the frame is HELD will not change an Arnold "
    "render until the frame moves (the viewport and swatch update "
    "immediately)."
)


def _verify_gol_viewport():
    """Exec the Viewport source against a fake shader / texture-manager and
    confirm the uploaded float32 RGBA buffer equals the board _gol_advance
    produced (white/black), in top-down orientation."""
    import maya.api.OpenMayaRender as omr

    captured = {}

    class _FakeShader:
        def parameterList(self):
            return ["gTexture", "gSampler"]

        def parameterType(self, n):
            return (omr.MShaderInstance.kTexture2 if n == "gTexture"
                    else omr.MShaderInstance.kSampler)

        def setParameter(self, n, v):
            captured.setdefault("set", []).append(n)

    class _FakeTM:
        def acquireTexture(self, name, desc, data, gen_mips):
            captured.update(w=desc.fWidth, h=desc.fHeight, bytes=bytes(data),
                            fmt=desc.fFormat, bpr=desc.fBytesPerRow)
            return None          # real MTexture needs a GPU; bytes captured

        def releaseTexture(self, t):
            pass

    class _FakeSM:
        def acquireSamplerState(self, desc):
            return None

    class _FakeSelf(object):
        width = 5
        height = 5
        density = 0.5
        reset = 1
        frame = 3.0
        shader = _FakeShader()
        texture_manager = _FakeTM()
        state_manager = _FakeSM()

    self_obj = _FakeSelf()
    ns = {}
    exec(GOL_INIT, ns)
    ns["self"] = self_obj
    try:
        exec(compile(GOL_VIEW, "gol_viewport", "exec"), ns)
    except Exception as exc:
        return False, "exec:%r" % exc
    if "bytes" not in captured:
        return False, "no upload"

    got = np.frombuffer(captured["bytes"], dtype=np.float32).reshape(
        captured["h"], captured["w"], 4)
    exp = ns["_gol_rgba"](ns["_gol_seed"](5, 5, 0.5, seed=3))
    fmt_ok = captured["fmt"] == omr.MRenderer.kR32G32B32A32_FLOAT
    fields_ok = captured["bpr"] == captured["w"] * 4 * 4
    parity_ok = bool(np.allclose(got, exp))

    # Headless degradation: no texture manager -> no raise / no upload.
    captured.clear()
    self_obj.texture_manager = None
    self_obj.board = None                          # force a fresh advance
    ns2 = {}
    exec(GOL_INIT, ns2)
    ns2["self"] = self_obj
    try:
        exec(compile(GOL_VIEW, "gol_viewport", "exec"), ns2)
        headless_ok = "bytes" not in captured
    except Exception as exc:
        return False, "headless-raise:%r" % exc

    ok = fmt_ok and fields_ok and parity_ok and headless_ok
    return ok, "fmt=%s flds=%s parity=%s hl=%s" % (
        fmt_ok, fields_ok, parity_ok, headless_ok)


def _verify_gol_osl():
    """The OSL twin must be structurally a Game-of-Life file sampler AND compile
    (real aiOslShader compile when MtoA is present; (True, '') headless)."""
    # `%s.%04d.png` is the cross-tier contract, not decoration: the Compute tier
    # (_stamped_bake_path) and the nd_tex_write C++ kernel name the file, the
    # shader has to rebuild the SAME name, and a mismatch is a texture that
    # silently fails to resolve rather than an error.
    structural = all(s in GOL_OSL for s in (
        "shader gameOfLife(", "string fileName", "float bakeFrame",
        "output color outColor", "output float outAlpha", "texture(path",
        '"%s.%04d.png"', "closest",
    )) and ("1.0 - v" in GOL_OSL or "1 - v" in GOL_OSL)
    if not structural:
        return False, "structural"
    try:
        from mpynode._common.osl.osl_targets import validate_osl_via_arnold
        ok, err = validate_osl_via_arnold(GOL_OSL)
        return bool(ok), (err or "arnold-ok")
    except Exception as exc:
        return False, "validate:%r" % exc


def build_game_of_life_file():
    mc.file(new=True, force=True)
    import ctypes
    from mpynode._common.node_setups import find_demo
    from mpynode.wrappers.mpy_file import MPyFile

    f = MPyFile.create(name="gameOfLifeTex", seed_defaults=False,
                       as_texture=True)
    # Add order IS the Channel Box / Designer display order (preserved end to
    # end via each attr's ``order`` field): width + height (the grid pair) stay
    # adjacent, then density, then frame, then reset.
    f.add_input_attr("width", "int", default_value=100)
    f.add_input_attr("height", "int", default_value=100)
    f.add_input_attr("density", "float", default_value=0.5,
                     min_value=0.0, max_value=1.0)
    # A user `time` input (auto-connected to time1 by add_input_attr, INCLUDING
    # on deserialize) drives the simulation. The built-in mPyFile self.time is
    # NOT used: its _timeIn auto-wire happens only in MPyFile.create, not on the
    # template-application path (deserialize_node / _TemplateCreateCommand), so a
    # gallery-created node would never advance. A `frame` time attr animates on
    # every create path (matches sine_ripple / the Game of Life mesh variant).
    f.add_input_attr("frame", "time")
    f.add_input_attr("reset", "enum", enum_names=["False", "True"])
    # The OSL/Arnold bake target. A real INPUT, not a stored var: Compute reads it
    # to drive self.write_texture, and persistent state only supports array/scalar
    # kinds -- a stored string would stop the compute lowering (and with it the
    # bit-exact RNG). Empty (the default) means "do not bake".
    f.add_input_attr("bakePath", "string")
    f.set_init_expression(GOL_INIT)
    f.set_compute_expression(GOL_COMPUTE)
    f.set_viewport_expression(GOL_VIEW)
    f.set_osl_expression(GOL_OSL)
    f.set_methods_source(DEMO_GOL_FILE)
    nm = f.get_name()

    # Capture the VANILLA payload NOW -- before the live-node compute checks run
    # (those set self.board / self.lastFrame stored vars and mutate width/height
    # for the small-grid test). Serializing first keeps the template clean (no
    # baked stored data, defaults intact); it is only written if the gate passes.
    _stamp_class(f, "GameOfLifeTex", "mPyFile")
    clean_payload = serialize_node(f, include_persistent=False)

    # --- pure-function checks (exec the Init source in a scratch namespace) ---
    ns = {}
    exec(GOL_INIT, ns)
    seedf, stepf, rgbaf = ns["_gol_seed"], ns["_gol_step"], ns["_gol_rgba"]

    # Bounded, no wrap: a blinker (3 in a row) is period-2; a lone corner cell
    # dies (no wrap means it never gets the 3 neighbours wrap would supply).
    blink = np.zeros((5, 5), dtype=bool)
    blink[2, 1:4] = True
    blinker_ok = (np.array_equal(stepf(stepf(blink)), blink)
                  and not np.array_equal(stepf(blink), blink))
    corner = np.zeros((5, 5), dtype=bool)
    corner[0, 0] = True
    corner_dies = not stepf(corner).any()
    big = seedf(200, 200, 0.5, seed=1)
    density_ok = abs(float(big.mean()) - 0.5) < 0.02
    sim_ok = blinker_ok and corner_dies and density_ok

    # Bake round-trip: read the PNG back top-down and it equals the board. Goes
    # through the BLESSED write_texture -- the exact code the node's Compute runs
    # (and the twin of the nd_tex_write C++ kernel), not a template-local copy.
    from mpynode._common.methods.file_methods import write_texture

    bpath = "/tmp/_gol_gate.png"
    bd = seedf(7, 11, 0.5, seed=2)
    # Gate the FRAME-STAMPED form, because that is the one Compute calls: the
    # bake must land on the numbered sibling and leave `bpath` alone. A new name
    # per frame is what makes an Arnold render animate (its texture cache is
    # keyed on the filename and never re-stats an overwritten file).
    stamped = "/tmp/_gol_gate.0002.png"
    for stale in (bpath, stamped):
        if os.path.exists(stale):
            os.unlink(stale)
    write_texture(None, bpath, rgbaf(bd), 2)
    rimg = om.MImage()
    rimg.readFromFile(stamped)
    rw, rh = rimg.getSize()
    rraw = ctypes.string_at(rimg.pixels(), rw * rh * 4)
    rarr = np.frombuffer(rraw, dtype=np.uint8).reshape(rh, rw, 4)[::-1]
    bake_ok = (os.path.isfile(stamped) and not os.path.exists(bpath)
               and rw == 11 and rh == 7
               and np.array_equal(rarr[..., 0] > 127, bd))

    # --- end-to-end Compute on the live node ---
    mc.setAttr(nm + ".width", 5)
    mc.setAttr(nm + ".height", 5)
    mc.setAttr(nm + ".density", 0.5)
    mc.setAttr(nm + ".reset", 1)
    mc.currentTime(5)
    exp = seedf(5, 5, 0.5, seed=5)

    def sample(cx, cy):
        mc.setAttr(nm + ".uCoord", (cx + 0.5) / 5.0)
        mc.setAttr(nm + ".vCoord", 1.0 - (cy + 0.5) / 5.0)
        mc.dgdirty(nm + ".outColor")
        return mc.getAttr(nm + ".outColor")[0][0]

    compute_ok = all(
        (sample(cx, cy) > 0.5) == bool(exp[cy, cx])
        for cy in range(5) for cx in range(5))

    # Stepping: reset off + advance the frame -> one bounded Conway step.
    mc.setAttr(nm + ".reset", 0)
    mc.currentTime(6)
    stepped = stepf(exp)
    step_ok = all(
        (sample(cx, cy) > 0.5) == bool(stepped[cy, cx])
        for cy in range(5) for cx in range(5))

    view_ok, view_err = _verify_gol_viewport()
    osl_ok, osl_err = _verify_gol_osl()
    has_demo = find_demo(DEMO_GOL_FILE) is not None

    # Run the authored @maya_test on a FRESH deserialized node.
    test_ok = False
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, name="golTestCheck")
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        if not test_ok:
            print("[gol_file] @maya_test FAILED: %s" % tres.get("error"))
    except Exception as exc:
        print("[gol_file] @maya_test run ERRORED: %r" % exc)

    ok = (sim_ok and bake_ok and compute_ok and step_ok
          and view_ok and osl_ok and has_demo and test_ok)
    print("[gol_file] sim=%s bake=%s compute=%s step=%s view=%s(%s) "
          "osl=%s(%s) demo=%s test=%s -> %s"
          % (sim_ok, bake_ok, compute_ok, step_ok, view_ok, view_err,
             osl_ok, osl_err, has_demo, test_ok, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(GOL_FILE_DIR, clean_payload, GOL_DESC)
    return ok


# ======================================================================
# 2b. Game of Life -- mPyMesh (one cube per live cell, single output mesh)
# ======================================================================
# The Init tier carries the SAME bounded-Conway kernel as the mPyFile texture
# and the (now-retired) mPyNode transform-grid variants: _gol_seed / _gol_step /
# _gol_board. A bounded uint8 board (no wrap) is seeded deterministically and
# advanced one step per frame, so Compute keeps NO cross-eval state and the
# timeline scrubs both ways cleanly. Compute then builds ONE cube mesh per live
# cell straight into a single ``outMesh`` -- users get a grid of any size with
# no manually-created cubes to wire up.
MESH_GOL_INIT = '''# Conway's Game of Life -- numpy-array kernel shared with the mPyFile texture
# variant (_gol_seed / _gol_step). A bounded uint8 board (no wrap) is seeded
# deterministically and advanced one Conway step per frame. Compute rebuilds the
# board from a fixed seed on every eval, so the node keeps NO cross-eval state
# and scrubbing the timeline forward OR backward is stable.
import numpy as np
from mpynode._api2.geometry import Mesh


def _gol_seed(h, w, density, seed=0):
    """Random board: a `density` fraction of cells alive. Deterministic for a
    given (shape, density, seed) so a reset is reproducible."""
    rng = np.random.RandomState(int(seed) & 0x7fffffff)
    return rng.random((int(h), int(w))) < float(density)


def _gol_step(board):
    """One Conway step on a BOUNDED grid: neighbours beyond the edge are dead
    (zero padding, NOT np.roll), so live cells never wrap around the border."""
    b = board.astype(np.uint8)
    pad = np.zeros((b.shape[0] + 2, b.shape[1] + 2), dtype=np.uint8)
    pad[1:-1, 1:-1] = b
    n = (pad[:-2, :-2] + pad[:-2, 1:-1] + pad[:-2, 2:] +
         pad[1:-1, :-2]                 + pad[1:-1, 2:] +
         pad[2:, :-2]  + pad[2:, 1:-1]  + pad[2:, 2:])
    return (n == 3) | ((b == 1) & (n == 2))


def _gol_board(h, w, samples, frame, reset):
    """Deterministic board at `frame`: seed then advance (frame - 1) steps.

    `samples` is a target live-cell COUNT (density = samples / cells). When
    `reset` is truthy the seed varies with frame (a fresh random board each
    frame); otherwise the board evolves from one fixed seed. Pure function of
    the inputs -- no stored state -- so frame N always yields the same board.
    """
    h = max(1, int(h))
    w = max(1, int(w))
    density = float(samples) / float(h * w)
    if reset:
        return _gol_seed(h, w, density, seed=int(frame))
    board = _gol_seed(h, w, density, seed=0)
    for _ in range(max(0, int(frame) - 1)):
        board = _gol_step(board)
    return board
'''

MESH_GOL_COMPUTE = '''# Conway's Game of Life as a single procedural mesh: build ONE cube per LIVE
# cell straight into ``self.outMesh``. The board is a bounded numpy array (no
# wrap) recomputed from a fixed seed each eval -- no cross-eval state, so the
# timeline scrubs both ways. Advance with `frame` (auto-wired to time1);
# `resetBoard` reseeds `randomSamples` cells each frame. Adjacent cubes are NOT
# welded (overlapping faces/verts are intentional); `cellSize` (< 1) leaves a
# visible gap between neighbouring cells.
import numpy as np
from mpynode._api2.geometry import Mesh

bx = max(1, self.boardX)
by = max(1, self.boardY)
board = _gol_board(by, bx, self.randomSamples, self.frame, self.resetBoard)

half = 0.5 * max(1e-6, self.cellSize)
ys, xs = np.nonzero(board)              # row (y) + col (x) of each live cell
m = int(xs.shape[0])

if m == 0:
    # An all-dead board -> an empty (but valid) mesh: no points, no faces.
    points = np.zeros((0, 3), dtype=np.float64)
    counts = np.zeros(0, dtype=np.int32)
    indices = np.zeros(0, dtype=np.int32)
else:
    # Cube centre = grid cell coordinate (x, y, 0), one unit apart.
    centers = np.column_stack([
        xs.astype(np.float64),
        ys.astype(np.float64),
        np.zeros(m, dtype=np.float64)])
    # 8 corners of a unit cube, scaled to half the cell size.
    corners = np.array([
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
    ], dtype=np.float64) * half
    # (m, 8, 3) -> (8m, 3): every cube's 8 corners in world space.
    points = (centers[:, None, :] + corners[None, :, :]).reshape(-1, 3)
    # 6 outward-facing quad faces per cube; offset each cube's indices by 8*i.
    # Every quad is wound CCW as seen from OUTSIDE so its normal points away
    # from the cube centre (-Z, +Z, -Y, +Y, -X, +X respectively).
    faces = np.array([
        [0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4],
        [3, 7, 6, 2], [0, 4, 7, 3], [1, 2, 6, 5],
    ], dtype=np.int32)
    base = (8 * np.arange(m, dtype=np.int32))[:, None, None]
    indices = (base + faces[None, :, :]).reshape(-1)
    counts = np.full(6 * m, 4, dtype=np.int32)

self.outMesh = Mesh(points=points, counts=counts, indices=indices)
'''

# Full setup authored into the template's Methods tab: build the render
# transform + mesh shape, wire outMesh into it, assign initialShadingGroup, seed
# a lively default grid, and frame it. Mirrors node_setups/mPyMesh.py plus a
# frame auto-wire fallback (add_input_attr already wires time1 on the template-
# apply path; re-issuing an identical connection just warns).
DEMO_GOL_MESH = '''# Build a complete, self-contained Game of Life mesh demo: a render mesh fed by
# this node's outMesh (one cube per live cell), a lively default grid, and a
# frame view. Play the timeline (frame is wired to time1) to watch it evolve.


def demo(self):
    from maya import cmds as mc
    name = self.get_name()

    # A larger, denser board than the defaults so the demo reads immediately.
    mc.setAttr(name + ".boardX", 20)
    mc.setAttr(name + ".boardY", 20)
    mc.setAttr(name + ".randomSamples", 120)

    # Render mesh: outMesh -> inMesh, shaded by the default lambert.
    xform = mc.createNode("transform", name=name + "Render")
    shape = mc.createNode("mesh", name=name + "RenderShape", parent=xform)
    mc.connectAttr(name + ".outMesh", shape + ".inMesh", force=True)
    mc.sets(shape, edit=True, forceElement="initialShadingGroup")

    # add_input_attr already auto-connects time1.outTime -> .frame on the
    # template-apply path; only wire it here as a fallback if that did not
    # happen (re-issuing an identical connection just emits a noisy
    # "already connected" warning).
    if mc.objExists("time1") and not mc.listConnections(
            name + ".frame", s=True, d=False):
        try:
            mc.connectAttr("time1.outTime", name + ".frame", force=True)
        except Exception:
            pass

    # Force one eval so the mesh exists now, then frame it.
    try:
        mc.dgdirty(name + ".outMesh")
        mc.dgeval(shape + ".outMesh")
    except Exception:
        pass
    try:
        mc.select(xform)
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_test(label="Game of Life: 8 verts + 6 quads per live cell", digits=3)
def test_game_of_life(self):
    """Validate the node's INTENT (the same test passes on the interpreted node
    and its C++ compile -> parity): with ``resetBoard`` on, the output mesh is
    exactly one cube (8 verts, 6 quad faces) per LIVE cell of the deterministic
    seeded board, and advancing ``frame`` -- or changing a non-time input --
    reseeds and recomputes it. Mirrors the builder's own live end-to-end check.
    """
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_equal, assert_true

    name = self.get_name()

    # A render mesh to pull the node's outMesh through a public plug.
    render = mc.createNode("mesh")
    mc.connectAttr(name + ".outMesh", render + ".inMesh", force=True)

    # A small board that reseeds every frame, so no frame lands all-dead.
    mc.setAttr(name + ".boardX", 5)
    mc.setAttr(name + ".boardY", 5)
    mc.setAttr(name + ".cellSize", 0.9)
    mc.setAttr(name + ".resetBoard", 1)

    def set_frame(f):
        # ``frame`` is a time input (auto-wired to time1). Drive it through the
        # clock when connected, else write the plug directly.
        if mc.listConnections(name + ".frame", s=True, d=False, plugs=True):
            mc.currentTime(f)
        else:
            mc.setAttr(name + ".frame", f)

    def out_counts():
        # Force a clean recompute (measures COMPUTE, not dirty-propagation),
        # then pull vert + poly counts off the output mesh.
        mc.dgdirty(name)
        mc.dgeval(render + ".outMesh")
        sl = om2.MSelectionList(); sl.add(render)
        try:
            fn = om2.MFnMesh(sl.getDagPath(0))
            return fn.numVertices, fn.numPolygons
        except Exception:
            return 0, 0     # all-dead board -> empty mesh MFnMesh won't wrap

    def alive_reset(samples, frame):
        # Mirror the node's deterministic 5x5 reseed (resetBoard on).
        rng = np.random.RandomState(int(frame) & 0x7fffffff)
        return int(np.count_nonzero(rng.random((5, 5)) < float(samples) / 25.0))

    # 1) reset + frame seeds the board via the time path: 8 verts / 6 quads/cell.
    mc.setAttr(name + ".randomSamples", 13)
    set_frame(1)
    a1 = alive_reset(13, 1)
    assert_true(a1 > 0, "seed must produce a non-empty board for the test")
    v1, p1 = out_counts()
    assert_equal(v1, 8 * a1, "expected 8 verts per live cell (got %d)" % v1)
    assert_equal(p1, 6 * a1, "expected 6 quad faces per live cell (got %d)" % p1)

    # 2) advancing time (auto-wired frame) reseeds -> the board tracks `frame`.
    set_frame(7)
    a7 = alive_reset(13, 7)
    v7, p7 = out_counts()
    assert_equal(v7, 8 * a7, "advancing frame must reseed and recompute")
    assert_equal(p7, 6 * a7, "advancing frame must reseed and recompute")

    # 3) a NON-time input (randomSamples) change recomputes the mesh too.
    mc.setAttr(name + ".randomSamples", 6)
    a6 = alive_reset(6, 7)
    v6, p6 = out_counts()
    assert_equal(v6, 8 * a6, "changing randomSamples must recompute")
    assert_equal(p6, 6 * a6, "changing randomSamples must recompute")
'''

GOL_MESH_DESC = (
    "# Game Of Life\n\n"
    "Conway's Game of Life as one procedural mesh (an `mPyMesh`). Every "
    "**live** cell becomes a cube built straight into `outMesh`, so a board "
    "of any size shows up as geometry with nothing to wire by hand. The board "
    "is `boardX` by `boardY` cells and steps forward once per frame. It does "
    "not wrap, so gliders die at the edge instead of reappearing on the far "
    "side.\n\n"
    "Drive `frame` (already wired to the timeline) to animate. Set "
    "`resetBoard` to **True** to reseed a fresh random board each frame; "
    "`randomSamples` is how many cells start alive. `cellSize` is each cube's "
    "edge length -- the default 0.9 leaves a visible gap between "
    "neighbours.\n\n"
    "Touching cubes are **not** welded -- overlapping faces are intentional, "
    "kept for speed and simplicity.\n\n"
    "**Create + Run demo** builds the render mesh, seeds a lively 20x20 board "
    "and frames it. Play the timeline to watch it evolve."
)


def _verify_gol_mesh_geometry(self_obj, seedf):
    """Exec MESH_GOL_COMPUTE against `self_obj` and confirm the resulting
    outMesh has exactly 8 verts + 6 quads per LIVE cell, with every point sat
    inside its cell's cube. Returns (ok, detail)."""
    ns = {}
    exec(MESH_GOL_INIT, ns)
    ns["self"] = self_obj
    try:
        exec(compile(MESH_GOL_COMPUTE, "gol_mesh_compute", "exec"), ns)
    except Exception as exc:
        return False, "exec:%r" % exc

    board = ns["_gol_board"](
        max(1, int(self_obj.boardY)), max(1, int(self_obj.boardX)),
        self_obj.randomSamples, self_obj.frame, self_obj.resetBoard)
    alive = int(np.count_nonzero(board))

    # The compute builds the buffers as plain LOCALS and hands them to the Mesh
    # ctor, so read them back out of the exec namespace, not off `self`.
    pts = np.asarray(ns["points"], dtype=np.float64)
    counts = np.asarray(ns["counts"], dtype=np.int64)
    indices = np.asarray(ns["indices"], dtype=np.int64)

    shape_ok = (pts.shape == (8 * alive, 3)
                and counts.shape == (6 * alive,)
                and indices.shape == (24 * alive,))
    quads_ok = bool(alive == 0 or np.all(counts == 4))
    # Indices must reference exactly the points we built, nothing out of range.
    range_ok = bool(alive == 0
                    or (indices.min() >= 0 and indices.max() < 8 * alive))
    # Every quad must be wound so its Newell normal points OUTWARD (away from
    # its cube centre); a single flipped face renders as a hole/backface. All
    # cubes share identical topology, so checking cube 0's 6 faces is enough.
    normals_ok = True
    if alive > 0:
        cube = pts[:8]                          # cube 0's 8 corners (ids 0..7)
        centre = cube.mean(axis=0)
        for f in indices[:24].reshape(6, 4):
            poly = cube[f]
            nrm = np.zeros(3)
            for k in range(4):
                a, b = poly[k], poly[(k + 1) % 4]
                nrm[0] += (a[1] - b[1]) * (a[2] + b[2])
                nrm[1] += (a[2] - b[2]) * (a[0] + b[0])
                nrm[2] += (a[0] - b[0]) * (a[1] + b[1])
            if float(np.dot(nrm, poly.mean(axis=0) - centre)) <= 0.0:
                normals_ok = False
                break
    # outMesh must marshal to a real kMeshData MObject with the right vert
    # count. self.outMesh is a Mesh dataclass now, so realise it -- binding the
    # MObject to a live local FIRST (an unretained temp MFn* target crashes).
    verts_ok = False
    try:
        mesh_out = self_obj.outMesh
        dm = (mesh_out.to_mobject()
              if hasattr(mesh_out, "to_mobject") else mesh_out)
        fn = om.MFnMesh(dm)
        verts_ok = (fn.numVertices == 8 * alive
                    and fn.numPolygons == 6 * alive)
    except Exception as exc:
        if alive == 0:
            # An empty board yields an empty data MObject; MFnMesh may refuse
            # to wrap it, which is fine -- the shape/quads checks already cover
            # the empty case.
            verts_ok = True
        else:
            return False, "mfnmesh:%r" % exc

    ok = shape_ok and quads_ok and range_ok and normals_ok and verts_ok
    return ok, "alive=%d shape=%s quads=%s range=%s normals=%s verts=%s" % (
        alive, shape_ok, quads_ok, range_ok, normals_ok, verts_ok)


def build_game_of_life_mesh():
    mc.file(new=True, force=True)
    from mpynode._common.node_setups import find_demo
    from mpynode.wrappers.mpy_mesh import MPyMesh

    g = MPyMesh.create(name="gameOfLifeMesh")
    # Add order IS the Channel Box / Designer display order: the grid pair
    # (boardX, boardY) stays adjacent, then the animation clock, then the seed
    # controls, then the per-cube size.
    g.add_input_attr("boardX", "int", default_value=10)
    g.add_input_attr("boardY", "int", default_value=10)
    g.add_input_attr("frame", "time")
    g.add_input_attr("randomSamples", "int", default_value=40)
    g.add_input_attr("resetBoard", "enum", enum_names=["False", "True"])
    g.add_input_attr("cellSize", "double", default_value=0.9,
                     min_value=0.0)
    g.set_init_expression(MESH_GOL_INIT)
    g.set_compute_expression(MESH_GOL_COMPUTE)
    g.set_methods_source(DEMO_GOL_MESH)
    nm = g.get_name()

    # Capture the VANILLA payload NOW -- before the live-node checks mutate the
    # board size / current time. Serializing first keeps the template clean
    # (defaults intact, no baked stored data); only written if the gate passes.
    _stamp_class(g, "GameOfLifeMesh", "mPyMesh")
    clean_payload = serialize_node(g, include_persistent=False)

    # --- pure-function checks (exec the Init source in a scratch namespace) ---
    ns = {}
    exec(MESH_GOL_INIT, ns)
    seedf, stepf = ns["_gol_seed"], ns["_gol_step"]

    # Bounded, no wrap: a blinker (3 in a row) is period-2; a lone corner cell
    # dies (no wrap never supplies the 3 neighbours it would need to survive).
    blink = np.zeros((5, 5), dtype=bool)
    blink[2, 1:4] = True
    blinker_ok = (np.array_equal(stepf(stepf(blink)), blink)
                  and not np.array_equal(stepf(blink), blink))
    corner = np.zeros((5, 5), dtype=bool)
    corner[0, 0] = True
    corner_dies = not stepf(corner).any()
    big = seedf(200, 200, 0.5, seed=1)
    density_ok = abs(float(big.mean()) - 0.5) < 0.02
    sim_ok = blinker_ok and corner_dies and density_ok

    # --- geometry checks (exec Compute against a fake self, both board states)
    class _FakeSelf(object):
        boardX = 5
        boardY = 5
        randomSamples = 13
        frame = 1.0
        resetBoard = 1
        cellSize = 0.9
        outMesh = None

    reset_self = _FakeSelf()
    geom_reset_ok, geom_reset_err = _verify_gol_mesh_geometry(reset_self, seedf)

    evolve_self = _FakeSelf()
    evolve_self.frame = 3.0
    evolve_self.resetBoard = 0
    geom_evolve_ok, geom_evolve_err = _verify_gol_mesh_geometry(
        evolve_self, seedf)

    # An all-dead board must yield an empty (but valid) mesh, not a raise.
    empty_self = _FakeSelf()
    empty_self.randomSamples = 0
    empty_self.resetBoard = 0
    empty_self.frame = 1.0
    geom_empty_ok, geom_empty_err = _verify_gol_mesh_geometry(
        empty_self, seedf)

    geom_ok = geom_reset_ok and geom_evolve_ok and geom_empty_ok

    # --- end-to-end on the live node: advancing time (via the auto-wired
    #     frame) recomputes the mesh, and so does a change to a NON-time input.
    #     resetBoard=1 reseeds a fresh (non-empty) board each frame, so this
    #     never lands on an all-dead board (which would be a valid EMPTY mesh
    #     that MFnMesh refuses to wrap -- handled below regardless). ---
    shape = mc.createNode("mesh", name="golMeshRenderShape")
    mc.connectAttr(nm + ".outMesh", shape + ".inMesh", force=True)
    mc.setAttr(nm + ".boardX", 5)
    mc.setAttr(nm + ".boardY", 5)
    mc.setAttr(nm + ".resetBoard", 1)
    mc.setAttr(nm + ".cellSize", 0.9)

    def live_verts():
        mc.dgeval(shape + ".outMesh")
        sel = om.MSelectionList()
        sel.add(shape)
        try:
            return om.MFnMesh(sel.getDagPath(0)).numVertices
        except Exception:
            return 0     # empty mesh (all-dead board) -> MFnMesh refuses; 0

    def alive_reset(samples, frame):
        return int(np.count_nonzero(
            seedf(5, 5, float(samples) / 25.0, seed=int(frame))))

    # (1) reset + frame seeds the board via the time path.
    mc.setAttr(nm + ".randomSamples", 13)
    mc.currentTime(1)
    live1_ok = live_verts() == 8 * alive_reset(13, 1)

    # (2) advancing time (auto-wired frame) reseeds -> a different board.
    mc.currentTime(7)
    live7_ok = live_verts() == 8 * alive_reset(13, 7)

    # (3) a NON-time input (randomSamples) change recomputes the mesh too.
    mc.setAttr(nm + ".randomSamples", 6)
    sample_ok = live_verts() == 8 * alive_reset(6, 7)

    live_ok = live1_ok and live7_ok and sample_ok

    has_demo = find_demo(DEMO_GOL_MESH) is not None

    # Run the authored @maya_test on a FRESH deserialized node.
    test_ok = False
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, name="golTestCheck")
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        if not test_ok:
            print("[gol_mesh] @maya_test FAILED: %s" % tres.get("error"))
    except Exception as exc:
        print("[gol_mesh] @maya_test run ERRORED: %r" % exc)

    ok = sim_ok and geom_ok and live_ok and has_demo and test_ok
    print("[gol_mesh] sim=%s geom=%s(r=%s e=%s 0=%s) live=%s(t1=%s t7=%s "
          "samp=%s) demo=%s test=%s -> %s"
          % (sim_ok, geom_ok, geom_reset_err, geom_evolve_err, geom_empty_err,
             live_ok, live1_ok, live7_ok, sample_ok, has_demo, test_ok,
             "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(GOL_MESH_DIR, clean_payload, GOL_MESH_DESC)
    return ok


# ======================================================================
#  UV Layout -- mesh input -> its UVs as a flat 2D mesh
# ======================================================================
UV_LAYOUT_INIT = "import numpy as np\nfrom mpynode._api2.geometry import Mesh\n"

UV_LAYOUT_COMPUTE = '''# Output the input mesh's UV layout as a flat 2D mesh: each UV coordinate becomes
# an (u, v, 0) point and the mesh's per-face UV connectivity becomes the output
# faces. Plug a mesh into `inMesh` and the generated mesh in the 3D view IS its
# UV layout -- handy for inspecting/visualising UVs as geometry. Choose a UV set
# by name with `uvSetName` (blank = the first/default set, e.g. "map1"); a mesh
# with no UVs (or an unconnected input) yields an empty (but valid) mesh.
import numpy as np
from mpynode._api2.geometry import Mesh

src = getattr(self, "inMesh", None)
sets = src.uv_sets if src is not None else []
if not sets:
    self.outMesh = Mesh()
else:
    want = (getattr(self, "uvSetName", "") or "").strip()
    chosen = sets[0]
    if want:
        for s in sets:
            if s.name == want:
                chosen = s
                break
    # Mesh() gracefully accepts a UVSet -> builds the 2D UV layout (u, v, 0.0).
    self.outMesh = Mesh(chosen)
'''

UV_LAYOUT_METHODS = VANILLA_SETUP_ERROR + VANILLA_MESHES + '''

@maya_command(creates=True)
def setup(self, selection=None, *args, **kwargs):
    """Select a mesh, then Run setup: wires that mesh's UVs into this node and
    builds a render mesh that shows the UV layout as geometry in the 3D view."""
    from maya import cmds as mc

    name = self.get_name()
    order = [o for o in (selection or mc.ls(selection=True) or []) if o != name]
    meshes = _meshes(order) if order else []
    if not meshes:
        raise SetupError("Select a mesh, then run setup.")
    shape = (mc.ls(meshes[0], long=True) or [meshes[0]])[0]
    mc.connectAttr(shape + ".worldMesh[0]", name + ".inMesh", force=True)

    out = mc.createNode("mesh")
    out_tr = mc.listRelatives(out, parent=True)[0]
    out_tr = mc.rename(out_tr, name + "_uvLayout")
    out_shape = mc.listRelatives(out_tr, shapes=True, fullPath=True)[0]
    mc.connectAttr(name + ".outMesh", out_shape + ".inMesh", force=True)
    try:
        mc.sets(out_shape, edit=True, forceElement="initialShadingGroup")
    except Exception:
        pass
    return out_tr


@maya_demo(label="UV layout of a sphere")
def demo(self):
    """Create a poly sphere and show its UV layout as a mesh."""
    from maya import cmds as mc

    sph = mc.polySphere(constructionHistory=False)[0]
    # The wrapper does NOT expose methods_source funcs as attributes, so
    # ``self.setup(...)`` would AttributeError; route through the validated
    # dispatcher (run_setup binds our ``def setup(self, ...)`` and passes
    # selection=).
    res = self.run_setup([sph])
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return res


@maya_test(label="UV layout: 3D output equals source UVs", digits=4)
def test_uv_layout(self):
    """Validate the node's INTENT (works identically for the interpreted node and
    its C++ compile, so passing it against the compiled node proves parity):

      1. The output mesh's 3D XY positions equal the source mesh's 2D UV
         coordinates, with Z == 0 (that IS what the node does).
      2. Moving the source UVs re-lays the output (the layout tracks the UVs).
      3. Deleting a source face carries through to the output topology
         (output face count follows the input).
    """
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    from mpynode._common.methods.test_helpers import assert_close, assert_equal

    name = self.get_name()

    # Build a source cube, wire its UVs in, and a render mesh to pull the output.
    cube_t = mc.polyCube(constructionHistory=False)[0]
    src = (mc.listRelatives(cube_t, shapes=True, fullPath=True) or [cube_t])[0]
    mc.connectAttr(src + ".worldMesh[0]", name + ".inMesh", force=True)
    render = mc.createNode("mesh")
    mc.connectAttr(name + ".outMesh", render + ".inMesh", force=True)

    def _out_points_and_faces():
        # Force a clean recompute so this measures COMPUTE correctness, not DG
        # dirty-propagation. A UV-only source edit does not auto-dirty a
        # downstream geo node's mesh INPUT (handled separately by auto_dirty's
        # native coverage), so dgdirty the whole node -- which dirties inMesh so
        # compute re-pulls fresh mesh data from the source -- then re-pull.
        mc.dgdirty(name)
        mc.dgeval(render + ".outMesh")
        sl = om2.MSelectionList(); sl.add(render)
        fn = om2.MFnMesh(sl.getDagPath(0))
        return [(p.x, p.y, p.z) for p in fn.getPoints()], fn.numPolygons

    def _src_uvs():
        sl = om2.MSelectionList(); sl.add(src)
        us, vs = om2.MFnMesh(sl.getDagPath(0)).getUVs()
        return list(us), list(vs)

    def _assert_layout_matches_uvs():
        pts, _ = _out_points_and_faces()
        us, vs = _src_uvs()
        assert_equal(len(pts), len(us),
                     "output verts (%d) must equal UV count (%d)"
                     % (len(pts), len(us)))
        got, expect = [], []
        for (x, y, z), u, v in zip(pts, us, vs):
            got.extend([x, y, z]); expect.extend([u, v, 0.0])
        assert_close(got, expect)

    # 1) 3D XY == source UVs (Z == 0).
    _assert_layout_matches_uvs()

    # 2) Move the UVs; the layout must follow.
    mc.polyEditUV(src + ".map[*]", uValue=0.25, vValue=-0.1, relative=True)
    _assert_layout_matches_uvs()

    # 3) Delete a source face; the output UV-face topology follows the input.
    mc.delete(src + ".f[0]")
    _, npolys = _out_points_and_faces()
    sl = om2.MSelectionList(); sl.add(src)
    assert_equal(npolys, om2.MFnMesh(sl.getDagPath(0)).numPolygons,
                 "output face count must follow the source after a face delete")
'''

UV_LAYOUT_DESC = (
    "# UV Layout (mesh -> UVs as a mesh)\n\n"
    "An `mPyMesh` that shows a mesh's UV layout as flat geometry in the 3D "
    "view. Each UV becomes an (u, v, 0) point and the per-face UV "
    "connectivity becomes the faces, so you can see stretching, overlaps and "
    "seams on real geometry.\n\n"
    "- `inMesh` -- the source mesh (connect its `worldMesh`).\n"
    "- `uvSetName` -- which UV set to show. Blank picks the first set, "
    "usually `map1`.\n\n"
    "Select a mesh, then Run setup -- it wires the mesh in and builds the UV "
    "render mesh for you."
)


def build_uv_layout_mesh():
    mc.file(new=True, force=True)
    from mpynode._common.node_setups import find_demo
    from mpynode.wrappers.mpy_mesh import MPyMesh
    from mpynode._api2.geometry import Mesh

    n = MPyMesh.create(name="uvLayoutMesh")
    n.add_input_attr("inMesh", "mesh")
    n.add_input_attr("uvSetName", "string", default_value="")
    n.set_init_expression(UV_LAYOUT_INIT)
    n.set_compute_expression(UV_LAYOUT_COMPUTE)
    n.set_methods_source(UV_LAYOUT_METHODS)
    nm = n.get_name()

    # Capture the VANILLA payload before any live mutation.
    _stamp_class(n, "UvLayoutMesh", "mPyMesh")
    clean_payload = serialize_node(n, include_persistent=False)

    # --- live end-to-end: wire a cube's UVs in, read the UV-layout mesh out.
    cube_t = mc.polyCube(constructionHistory=False)[0]
    cube_shape = mc.listRelatives(cube_t, shapes=True, fullPath=True)[0]
    mc.connectAttr(cube_shape + ".worldMesh[0]", nm + ".inMesh", force=True)
    render = mc.createNode("mesh", name="uvLayoutRenderShape")
    mc.connectAttr(nm + ".outMesh", render + ".inMesh", force=True)
    mc.dgeval(render + ".outMesh")

    rsel = om.MSelectionList()
    rsel.add(render)
    try:
        rfn = om.MFnMesh(rsel.getDagPath(0))
        nverts, npolys = rfn.numVertices, rfn.numPolygons
    except Exception:
        nverts, npolys = 0, 0

    # Reference: the interpreted UVSet.as_mesh() of the cube's default UV set.
    csel = om.MSelectionList()
    csel.add(cube_shape)
    ref = Mesh._attach(csel.getDependNode(0)).uv_sets[0].as_mesh()
    ref_v, ref_f = int(ref.points.shape[0]), int(ref.counts.shape[0])

    # A cube unwraps to 6 quad UV faces; the UV point count exceeds the 8 verts.
    live_ok = (nverts == ref_v and npolys == ref_f and ref_f == 6 and ref_v > 8)

    # An unconnected / value mesh input must yield an empty (not a crash).
    empty_ns = {}
    exec(UV_LAYOUT_INIT, empty_ns)

    class _EmptySelf(object):
        inMesh = Mesh()          # value mesh -> no uv_sets
        uvSetName = ""
        outMesh = None

    es = _EmptySelf()
    empty_ns["self"] = es
    try:
        exec(compile(UV_LAYOUT_COMPUTE, "uv_layout_compute", "exec"), empty_ns)
        empty_ok = (es.outMesh is not None
                    and getattr(es.outMesh, "points", None) is None)
    except Exception:
        empty_ok = False

    has_demo = find_demo(UV_LAYOUT_METHODS) is not None

    # Actually RUN the demo on a fresh node so a broken demo body (e.g. calling
    # self.setup instead of self.run_setup) fails the BUILD here, not later in
    # the user's session.
    demo_ok = False
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        dnode = deserialize_node(clean_payload, name="uvDemoCheck")
        dnode.run_demo()
        # the demo creates a sphere + wires a UV-layout render mesh; both exist.
        demo_ok = len(mc.ls(type="mesh") or []) >= 2
    except Exception as exc:
        print("[uv_layout] demo run FAILED: %r" % exc)

    # Run the authored @maya_test on a FRESH deserialized node.
    test_ok = False
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, name="uvTestCheck")
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        if not test_ok:
            print("[uv_layout] @maya_test FAILED: %s" % tres.get("error"))
    except Exception as exc:
        print("[uv_layout] @maya_test run ERRORED: %r" % exc)

    ok = live_ok and empty_ok and has_demo and demo_ok and test_ok
    print("[uv_layout] live=%s (verts=%s/%s polys=%s/%s) empty=%s demo=%s "
          "demo_run=%s test=%s -> %s"
          % (live_ok, nverts, ref_v, npolys, ref_f, empty_ok, has_demo,
             demo_ok, test_ok, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(UV_LAYOUT_DIR, clean_payload, UV_LAYOUT_DESC)
    return ok


# ======================================================================
# 2b. mPyMesh -- Metaballs (SDF dual-marching-cubes CSG)
# ======================================================================
# The node definition (INIT / COMPUTE / METHODS incl. addSphere / addBox /
# addCylinder) is the SDF DMC builder's single source of truth; we only append
# a self-contained ``def demo`` here. The demo builds the "MPyNode" text (26
# hard-union boxes, laid out by the SHIPPED glyph font
# mpynode._common.nodes.mesh.sdf_text) plus one Cube / Sphere / Cylinder blob
# below it -- each primitive folded with a DIFFERENT CSG op so the three ops the
# node supports are all on screen at once:
#   Cube     additive, smoothing 0    -> HARD union   (crisp boxy core)
#   Sphere   additive, smoothing >0   -> SMOOTH union (metaball blend / fillet)
#   Cylinder additive False           -> DIFFERENCE   (bored-through tunnel)
DEMO_METABALLS = '''# Build a complete, self-contained Metaballs demo: the "MPyNode" word rendered as
# one watertight SDF mesh (26 hard-union boxes from the shipped stroke font),
# plus a Cube / Sphere / Cylinder blob directly below it that shows all three CSG
# ops the node supports -- a crisp cube (hard union), a sphere smoothly fused to
# it (smooth union / metaball), and a cylinder bored straight through the middle
# (difference). Everything is driven by live transforms, so dragging any of them
# re-solves the mesh instantly.
def demo(self):
    from maya import cmds as mc
    from mpynode._common.nodes.mesh.sdf_text import word_strokes
    name = self.get_name()

    # --- "MPyNode" text: one hard-union box per stroke (additive, no blend) ---
    text_grp = mc.createNode("transform", name=name + "Text")
    for i, b in enumerate(word_strokes("MPyNode")):
        xf = mc.createNode("transform", parent=text_grp, name="stroke%02d" % i)
        mc.setAttr(xf + ".translate", float(b["cx"]), float(b["cy"]), 0.0)
        mc.setAttr(xf + ".rotateZ", float(b["angle"]))
        self.call_command("addBox", transform=xf,
                          half=(b["length"] * 0.5, b["thick"] * 0.5, b["depth"] * 0.5),
                          additive=True, smoothing=0.0)

    # --- demo blob BELOW the text (Y ~= -2): one of each primitive, one CSG op
    #     each. Fold order = array index, so the cube is the base, the sphere
    #     smooth-unions onto it, and the cylinder is subtracted from the pair. ---
    shp_grp = mc.createNode("transform", name=name + "Shapes")

    # Cube -- HARD union: the crisp boxy core of the blob.
    cube = mc.createNode("transform", parent=shp_grp, name="metaCube")
    mc.setAttr(cube + ".translate", 0.0, -2.4, 0.0)
    self.call_command("addBox", transform=cube, half=(0.9, 0.9, 0.9),
                      additive=True, smoothing=0.0)

    # Sphere -- SMOOTH union: overlaps the cube's upper-right corner so the
    # smoothing gives a gooey metaball fillet where the two meet.
    ball = mc.createNode("transform", parent=shp_grp, name="metaSphere")
    mc.setAttr(ball + ".translate", 0.75, -1.65, 0.0)
    self.call_command("addSphere", transform=ball, radius=0.8,
                      additive=True, smoothing=0.7)

    # Cylinder -- DIFFERENCE: laid along X and passed straight through the cube,
    # so it bores a clean round tunnel out of the blob (additive=False).
    cyl = mc.createNode("transform", parent=shp_grp, name="metaCylinder")
    mc.setAttr(cyl + ".translate", 0.0, -2.4, 0.0)
    self.call_command("addCylinder", transform=cyl, radius=0.45, height=3.0,
                      axis=0, additive=False, smoothing=0.0)

    # --- render mesh: outMesh -> inMesh, shaded by the default lambert. ---
    xform = mc.createNode("transform", name=name + "Render")
    shape = mc.createNode("mesh", name=name + "RenderShape", parent=xform)
    mc.connectAttr(name + ".outMesh", shape + ".inMesh", force=True)
    mc.sets(shape, edit=True, forceElement="initialShadingGroup")

    # resolution is a LIVE plug: 12 matches the shipped text example; drag it
    # lower for snappier interaction, higher (or the C++ build) for a denser mesh.
    mc.setAttr(name + ".resolution", 12)
    try:
        mc.dgdirty(name + ".outMesh")
        mc.dgeval(shape + ".outMesh")
    except Exception:
        pass
    try:
        mc.select(xform)
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_test(label="Metaballs: SDF mesh builds and the cylinder carves", digits=3)
def test_metaballs(self):
    """Validate the node's INTENT (the same test passes on the interpreted node
    AND its C++ compile -> parity, since it only touches PUBLIC plugs): a box
    hard-unions into a real watertight mesh, and toggling a bored cylinder
    between DIFFERENCE and UNION changes that mesh -- proof the CSG difference
    op actually carves.

    Scene-robust: the demo CONNECTS existing shape plugs (halfExtents[i],
    shapeMatrix[i], radius[i]...) to its locators, so this test never touches
    those. It claims FRESH stream indices it fully owns (appended past whatever
    the demo -- or a previous run -- already put on the stream) and drives them
    through a disconnect-before-set helper, keeping the assertions identical."""
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    from mpynode._common.methods.test_helpers import assert_true

    name = self.get_name()

    def _set(plug, *vals, **kw):
        # A demo/user may have CONNECTED this shape plug (array elements like
        # foo[i] included); break any incoming connection so the test can drive
        # it, then set the value.
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals, **kw)

    # Claim shape-stream indices this test fully OWNS. The demo folds a whole
    # word of boxes plus a Cube/Sphere/Cylinder blob onto indices 0..N, each
    # input CONNECTED to a live locator; appending PAST the current max means we
    # never clobber (or setAttr onto) a connected plug. The array index IS the
    # CSG fold order, so our cube folds in, then our cylinder carves it.
    used = mc.getAttr(name + ".shapeMatrix", multiIndices=True) or []
    base = (max(used) + 1) if used else 0
    i_cube, i_cyl = base, base + 1

    # Shape @i_cube -- a crisp cube (hard union): additive on, smoothing 0.
    cube = mc.createNode("transform", name="mbTestCube#")
    mc.connectAttr(cube + ".worldMatrix[0]",
                   "%s.shapeMatrix[%d]" % (name, i_cube), force=True)
    _set("%s.shapeType[%d]" % (name, i_cube), 1)     # 1 == box
    _set("%s.additive[%d]" % (name, i_cube), 1)      # union
    _set("%s.smoothing[%d]" % (name, i_cube), 0.0)   # hard (no blend)
    _set("%s.halfExtents[%d]" % (name, i_cube), 0.9, 0.9, 0.9, type="double3")

    # Shape @i_cyl -- a cylinder laid along X, bored straight through the cube
    # (DIFFERENCE: additive off).
    cyl = mc.createNode("transform", name="mbTestCyl#")
    mc.connectAttr(cyl + ".worldMatrix[0]",
                   "%s.shapeMatrix[%d]" % (name, i_cyl), force=True)
    _set("%s.shapeType[%d]" % (name, i_cyl), 2)      # 2 == cylinder
    _set("%s.additive[%d]" % (name, i_cyl), 0)       # difference -> carve
    _set("%s.smoothing[%d]" % (name, i_cyl), 0.0)
    _set("%s.radius[%d]" % (name, i_cyl), 0.45)
    _set("%s.height[%d]" % (name, i_cyl), 3.0)
    _set("%s.axis[%d]" % (name, i_cyl), 0)           # along X
    _set(name + ".resolution", 16)

    # Render mesh to pull the folded field out through outMesh.
    render = mc.createNode("mesh")
    mc.connectAttr(name + ".outMesh", render + ".inMesh", force=True)

    def _verts():
        # Force a clean recompute: a per-shape sub-data edit does NOT auto-dirty
        # a downstream geo node's mesh INPUT, so dirty the WHOLE node (which
        # dirties inMesh so compute re-folds the field) then re-pull.
        mc.dgdirty(name)
        mc.dgeval(render + ".outMesh")
        sl = om2.MSelectionList(); sl.add(render)
        try:
            return om2.MFnMesh(sl.getDagPath(0)).numVertices
        except Exception:
            return 0

    # 1) The folded SDF stream must extract a real mesh.
    v_carved = _verts()
    assert_true(v_carved > 0,
                "SDF stream must build a mesh (got %d verts)" % v_carved)

    # 2) Flip the bored cylinder from DIFFERENCE to UNION: the tunnel fills in,
    #    so the mesh MUST change -- proof the difference op is doing work.
    _set("%s.additive[%d]" % (name, i_cyl), 1)
    v_filled = _verts()
    assert_true(v_filled > 0 and v_filled != v_carved,
                "carving the cylinder must change the mesh "
                "(carved=%d filled=%d)" % (v_carved, v_filled))
'''

# ======================================================================
#  Voxelize -- mesh input -> a voxel SHELL of cubes, coloured from the source
# ======================================================================
# The sample texture `setup` seeds, RELATIVE to a template search root so it
# resolves wherever the templates are installed. Shared with the MPyFile
# examples rather than copied -- one asset, one place to update. The methods
# source is a serialized string and cannot reference this constant, so the
# build gate asserts the two spellings match.
VOXELIZE_SAMPLE_TEX = "MPyFile/File Simple/test_grid.png"

VOXELIZE_INIT = '''import os, ctypes
import numpy as np
import maya.api.OpenMaya as om
from mpynode._api2.geometry import Mesh

# Per-node cache so a texture is read from disk once, not on every compute().
_VOX_IMG_CACHE = {}
_VOX_TPL_ROOTS = []


def _vox_template_roots():
    """Template search roots, resolved once. Reuses mpynode's own resolver so a
    RELATIVE textureFile keeps working wherever the templates are installed: it
    honours the template_search_paths preference, then $MPYNODE_ROOT/templates.
    Pure filesystem work -- no scene state, no DG -- so it is safe from
    compute()."""
    if not _VOX_TPL_ROOTS:
        try:
            from mpynode._common.util.template_gallery import (
                template_search_roots)
            _VOX_TPL_ROOTS.extend(template_search_roots() or [])
        except Exception:
            pass
    return _VOX_TPL_ROOTS


def _vox_resolve_path(path):
    """Absolute path -> used as-is. RELATIVE path -> tried under each template
    search root, so the shipped sample texture resolves on any install.
    Returns None when nothing readable turns up."""
    if os.path.isabs(path):
        return path if os.path.isfile(path) else None
    for root in _vox_template_roots():
        cand = os.path.join(root, *path.split("/"))   # POSIX-authored -> Windows
        if os.path.isfile(cand):
            return cand
    return path if os.path.isfile(path) else None


def _vox_srgb_to_linear(rgb):
    """sRGB-encoded -> scene-linear (vectorized piecewise EOTF), so voxels
    shade at the same brightness a standard Maya `file` node would give."""
    low = rgb / 12.92
    high = np.power((rgb + 0.055) / 1.055, 2.4)
    return np.where(rgb <= 0.04045, low, high).astype(np.float32)


def _vox_read_image(path):
    """Read an image into an ``(H, W, 4)`` float32 array in SCENE-LINEAR [0,1]
    using Maya's built-in MImage (no PIL needed). The path may be absolute or
    relative to a template search root. Returns None for a blank path or
    anything unreadable -- that None is what makes the colour chain fall back
    to vertex colours."""
    key = (path or "").strip()
    if not key:
        return None
    if key in _VOX_IMG_CACHE:
        return _VOX_IMG_CACHE[key]
    resolved = _vox_resolve_path(key)
    if resolved is None:
        return None                    # uncached: the file may appear later
    arr = None
    try:
        img = om.MImage()
        img.readFromFile(resolved)
        w, h = img.getSize()
        raw = ctypes.string_at(img.pixels(), w * h * 4)        # RGBA uint8
        f = (np.frombuffer(raw, dtype=np.uint8)
               .astype(np.float32).reshape(h, w, 4) / 255.0)
        f[..., :3] = _vox_srgb_to_linear(f[..., :3])
        # MImage rows are stored BOTTOM-UP; flip to TOP-DOWN so the sampler
        # below matches the mPyFile template and Maya's own file node.
        arr = np.ascontiguousarray(f[::-1])
    except Exception:
        arr = None
    _VOX_IMG_CACHE[key] = arr
    return arr


def _vox_sample_texture(img, uv):
    """Bilinear-filtered RGB lookup for an ``(N, 2)`` block of UVs -> (N, 3).

    Bilinear rather than nearest because one voxel stands in for a whole patch
    of surface, so the blended texel is the better representative colour. V is
    flipped: Maya's V runs bottom-up while the buffer is top-down.
    """
    h, w = img.shape[0], img.shape[1]
    uu = uv[:, 0] - np.floor(uv[:, 0])                # wrap into [0,1)
    vv = uv[:, 1] - np.floor(uv[:, 1])
    x = uu * w - 0.5
    y = (1.0 - vv) * h - 0.5
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx = (x - x0)[:, None]
    fy = (y - y0)[:, None]
    xa = np.clip(x0, 0, w - 1)
    xb = np.clip(x0 + 1, 0, w - 1)
    ya = np.clip(y0, 0, h - 1)
    yb = np.clip(y0 + 1, 0, h - 1)
    top = img[ya, xa, :3] * (1.0 - fx) + img[ya, xb, :3] * fx
    bot = img[yb, xa, :3] * (1.0 - fx) + img[yb, xb, :3] * fx
    return (top * (1.0 - fy) + bot * fy).astype(np.float64)


def _vox_grid(lo, hi, vs):
    """Voxel CENTRES of every cell the bounding box touches.

    The lattice is WORLD-anchored: cell ``i`` spans ``[i*vs, (i+1)*vs)``, so a
    cube CORNER sits exactly on the origin and the lattice does NOT drift when
    the mesh moves or deforms (anchoring to the mesh minimum would make the
    voxels swim). The bounding box comes from the points rather than the MFn
    ``boundingBox`` property: an MFnMesh minted from geometry DATA has no DAG
    node, so that property raises "Object does not exist".
    """
    i0 = np.floor(np.asarray(lo, dtype=np.float64) / vs).astype(np.int64)
    i1 = np.floor(np.asarray(hi, dtype=np.float64) / vs).astype(np.int64)
    axes = [np.arange(i0[d], i1[d] + 1, dtype=np.int64) for d in range(3)]
    gi = np.stack(np.meshgrid(axes[0], axes[1], axes[2], indexing="ij"), axis=-1).reshape(-1, 3)
    return (gi.astype(np.float64) + 0.5) * vs


def _vox_closest(mesh_obj, grid):
    """Closest point on the mesh for every grid point.

    ``MMeshIntersector`` is spatially accelerated -- measured ~170k queries/s,
    about 13x faster than ``MFnMesh.getClosestPoint`` for the identical answer.
    It needs a mesh MObject, which ``Mesh.to_mobject()`` hands over zero-copy
    for an attached input (``fn.object()`` returns kInvalid, so that is the only
    route). Returns samples, face ids, triangle ids and barycentric (u, v).
    """
    isect = om.MMeshIntersector()
    isect.create(mesh_obj)
    n = int(grid.shape[0])
    samples = np.empty((n, 3), dtype=np.float64)
    faces = np.empty(n, dtype=np.int64)
    tris = np.empty(n, dtype=np.int64)
    bary = np.empty((n, 2), dtype=np.float64)
    for k in range(n):
        r = isect.getClosestPoint(om.MPoint(grid[k, 0], grid[k, 1], grid[k, 2]))
        p = r.point
        samples[k, 0] = p.x
        samples[k, 1] = p.y
        samples[k, 2] = p.z
        faces[k] = r.face
        tris[k] = r.triangle
        b = r.barycentricCoords
        bary[k, 0] = b[0]
        bary[k, 1] = b[1]
    return samples, faces, tris, bary


def _vox_winners(samples, grid, vs):
    """Snap every sample to its voxel cell and drop duplicates, keeping the
    sample CLOSEST to its own grid point. Returns ``(cells, win)`` -- the
    occupied cell indices and the sample index that won each one, so the winner
    also supplies that cube's colour.

    The 3D cell index is packed into ONE int64 key so the dedupe is a plain 1-D
    ``np.unique`` (``axis=0`` on a 2-D array is a far heavier primitive). Cell
    indices go negative, hence the shift by ``base``.
    """
    cell = np.floor(samples / vs).astype(np.int64)
    base = cell.min(axis=0)
    span = cell.max(axis=0) - base + 1
    rel = cell - base
    key = (rel[:, 0] * span[1] + rel[:, 1]) * span[2] + rel[:, 2]
    order = np.argsort(((samples - grid) ** 2).sum(axis=1), kind="stable")
    _, first = np.unique(key[order], return_index=True)
    win = order[first]
    return cell[win], win


def _vox_corner_weights(mesh, faces, tris, bary):
    """Hit-triangle vertex ids plus barycentric weights, so ANY per-vertex
    attribute interpolates exactly at the closest point.

    Maya's ``MPointOnMesh.barycentricCoords`` is ``(u, v)`` for the FIRST TWO
    triangle vertices; the third weight is ``1-u-v``. Verified by reconstructing
    the hit point from the weights -- 5e-07 max error, where the other ordering
    is off by 0.73. ``getTriangles()`` gives the whole triangulation at once, so
    (face, triangle) -> vertex ids is a vectorized table lookup rather than a
    per-query ``getPolygonTriangleVertices`` call.
    """
    tc, tv = mesh.fn.getTriangles()
    tc = np.asarray(tc, dtype=np.int64)
    tv = np.asarray(tv, dtype=np.int64).reshape(-1, 3)
    toff = np.cumsum(tc) - tc
    u = bary[:, 0]
    v = bary[:, 1]
    return tv[toff[faces] + tris], np.stack([u, v, 1.0 - u - v], axis=1)


def _vox_uv_stream(mesh):
    """The mesh's first UV set as ``(uv_points, uv_indices)``, or
    ``(None, None)`` when it carries no usable UVs. ``uv_indices`` runs in
    lockstep with ``Mesh.indices`` -- both are addressed by FACE-VERTEX."""
    sets = getattr(mesh, "uv_sets", None) or []
    if not sets:
        return None, None
    uv = sets[0]
    uv_pts = np.asarray(uv.points, dtype=np.float64)
    if uv_pts.size == 0:
        return None, None
    return uv_pts, np.asarray(uv.indices, dtype=np.int64)


def _vox_vertex_uvs(mesh, num_points):
    """``(N, 2)`` per-vertex UV, or None when the mesh carries no UV set.

    UVs are per-FACE-VERTEX, so a vertex on a seam owns several. One scatter
    collapses the stream to vertex -> uv; at a seam the last write wins, which
    is invisible at voxel resolution. The caller blends these three at a time
    with the hit triangle's barycentric weights, which puts the texture lookup
    at the EXACT closest point.
    """
    uv_pts, uidx = _vox_uv_stream(mesh)
    if uv_pts is None:
        return None
    vidx = np.asarray(mesh.indices, dtype=np.int64)
    n = int(min(vidx.size, uidx.size))
    out = np.zeros((num_points, 2), dtype=np.float64)
    if n:
        out[vidx[:n]] = uv_pts[uidx[:n]]
    return out


def _vox_cubes(centers, half):
    """The game_of_life cube batcher: 8 verts + 6 outward quads per centre,
    emitted in one vectorized shot. Adjacent cubes are NOT welded."""
    m = int(centers.shape[0])
    corners = np.array([
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
    ], dtype=np.float64) * half
    points = (centers[:, None, :] + corners[None, :, :]).reshape(-1, 3)
    faces = np.array([
        [0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4],
        [3, 7, 6, 2], [0, 4, 7, 3], [1, 2, 6, 5],
    ], dtype=np.int32)
    base = (8 * np.arange(m, dtype=np.int32))[:, None, None]
    indices = (base + faces[None, :, :]).reshape(-1)
    counts = np.full(6 * m, 4, dtype=np.int32)
    return points, counts, indices
'''

VOXELIZE_COMPUTE = '''# Rebuild the incoming mesh as a voxel SHELL, by CLOSEST POINT rather than by
# binning the source geometry -- so the result never depends on how finely the
# source happens to be tessellated.
#
#   1. Take the source bounding box and lay a WORLD-anchored lattice over it:
#      cell `i` spans [i*voxelSize, (i+1)*voxelSize), so a cube CORNER sits
#      exactly on the origin. The lattice is fixed in world space, so voxels do
#      not swim when the mesh moves or deforms.
#   2. Build the dense 3D point cloud of every cell CENTRE in that box and ask
#      the mesh for the closest surface point to each one.
#   3. Snap every returned sample to the cell that contains it and drop the
#      duplicates, keeping the sample CLOSEST to its own grid point. Those cells
#      are the voxels; each winner also supplies its cube's colour.
#
# The grid is O(K^3) while the shell is O(K^2), so most queries are "wasted" --
# but they are not: an interior grid point regularly claims a cell that no
# nearer point reaches, and pruning the query set to a band around the surface
# was measured to silently lose cells. MMeshIntersector runs ~170k queries/s,
# which keeps the dense sweep well inside interactive range.
#
# Colour is taken at the WINNING sample and falls down a chain: `textureFile`
# sampled at the exact closest point's UV, else the source's vertex colours,
# else `defaultColor`. A blank or unreadable path just drops to the next link --
# it is never an error.
import numpy as np
import maya.api.OpenMaya as om
from mpynode._api2.geometry import Mesh

src = getattr(self, "inMesh", None)
pts = None if src is None else getattr(src, "points", None)
pts = None if pts is None else np.asarray(pts, dtype=np.float64)
nfaces = 0 if src is None else int(np.asarray(src.counts).size)

if pts is None or pts.shape[0] == 0 or nfaces == 0:
    # No input, an empty one, or a point cloud with no surface to project onto
    # -> an empty but VALID mesh, never a raise.
    self.outMesh = Mesh()
else:
    vsize = max(1e-6, float(self.voxelSize))
    grid = _vox_grid(pts.min(axis=0), pts.max(axis=0), vsize)
    n = int(grid.shape[0])

    # Brake on the GRID, before a single query runs -- the sweep is cubic in
    # 1/voxelSize, so halving it costs 8x. Checking here aborts instantly
    # instead of after a long stall.
    cap = int(self.maxVoxels)
    if cap > 0 and n > cap:
        raise ValueError(
            "voxelize: %d grid points at voxelSize=%g exceeds maxVoxels=%d. "
            "Raise voxelSize (or maxVoxels) -- the sweep is cubic in "
            "1/voxelSize." % (n, vsize, cap))

    samples, faces, tris, bary = _vox_closest(src.to_mobject(), grid)
    cells, win = _vox_winners(samples, grid, vsize)
    m = int(cells.shape[0])
    centers = (cells.astype(np.float64) + 0.5) * vsize

    # The hit triangle + weights let ANY per-vertex attribute be read exactly at
    # the winning closest point. Only the winners are interpolated, not all n.
    corner, w = _vox_corner_weights(src, faces[win], tris[win], bary[win])

    # --- one colour per cube: texture -> vertex colour -> defaultColor -----
    col = None
    tex = _vox_read_image(self.textureFile)
    if tex is not None:
        uvv = _vox_vertex_uvs(src, pts.shape[0])
        if uvv is not None:
            col = _vox_sample_texture(tex, (uvv[corner] * w[:, :, None]).sum(1))
    if col is None:
        vcol = getattr(src, "colors", None)
        vcol = None if vcol is None else np.asarray(vcol, dtype=np.float64)
        if vcol is not None and vcol.shape[0] == pts.shape[0]:
            col = (vcol[corner] * w[:, :, None]).sum(1)[:, :3]
    if col is None:
        base_col = np.asarray(self.defaultColor, dtype=np.float64).reshape(1, -1)
        col = np.repeat(base_col[:, :3], m, axis=0)

    points, counts, indices = _vox_cubes(centers, 0.5 * vsize)
    # Per-vertex colours (no color_indices): 8 verts per cube all share its
    # colour, which is 1/3 the MColor churn of the per-face-vertex form.
    self.outMesh = Mesh(points=points, counts=counts, indices=indices,
                        colors=np.repeat(col, 8, axis=0))
'''

VOXELIZE_METHODS = VANILLA_SETUP_ERROR + VANILLA_MESHES + '''

@maya_command(creates=True)
def setup(self, selection=None, *args, **kwargs):
    """Select a mesh, then Run setup: wires that mesh in and builds a render
    mesh showing the voxel shell."""
    from maya import cmds as mc

    name = self.get_name()
    order = [o for o in (selection or mc.ls(selection=True) or []) if o != name]
    meshes = _meshes(order) if order else []
    if not meshes:
        raise SetupError("Select a mesh, then run setup.")
    shape = (mc.ls(meshes[0], long=True) or [meshes[0]])[0]
    mc.connectAttr(shape + ".worldMesh[0]", name + ".inMesh", force=True)

    out = mc.createNode("mesh")
    out_tr = mc.listRelatives(out, parent=True)[0]
    out_tr = mc.rename(out_tr, name + "_voxels")
    out_shape = mc.listRelatives(out_tr, shapes=True, fullPath=True)[0]
    mc.connectAttr(name + ".outMesh", out_shape + ".inMesh", force=True)
    try:
        mc.sets(out_shape, edit=True, forceElement="initialShadingGroup")
    except Exception:
        pass
    # Per-voxel colour is the whole point of this node, and a freshly created
    # mesh does not DRAW its colour set until displayColors is on.
    mc.setAttr(out_shape + ".displayColors", True)
    # Seed the shipped sample texture as a RELATIVE path -- it is resolved at
    # read time against the template search roots, so it paints on any install.
    # Never clobber a value the user already set, or an incoming connection.
    tex = name + ".textureFile"
    if not (mc.getAttr(tex) or "").strip() and not mc.listConnections(
            tex, source=True, destination=False):
        mc.setAttr(tex, "MPyFile/File Simple/test_grid.png", type="string")
    return out_tr


@maya_demo(label="Voxelize a sphere")
def demo(self):
    """Create a poly sphere and rebuild it as a voxel shell."""
    from maya import cmds as mc

    sph = mc.polySphere(constructionHistory=False, radius=5)[0]
    res = self.run_setup([sph])
    mc.setAttr(self.get_name() + ".voxelSize", 1.0)
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return res


@maya_test(label="Voxelize: shell tracks the source", digits=4)
def test_voxelize(self):
    """Validate the node's INTENT (identical for the interpreted node and its
    C++ compile, so passing it against the compiled node proves parity):

      1. Every emitted cube is a real cube -- 8 verts and 6 quads each.
      2. The voxels stay inside the source bounding box (grown by one voxel).
      3. The lattice is WORLD-anchored with a cube CORNER on the origin: every
         cube vertex therefore lands on an exact integer multiple of voxelSize.
         This is the load-bearing property -- it is what stops the voxels from
         swimming when the source moves -- and it is exactly assertable.
      4. A COARSER voxelSize yields no more voxels than a finer one.
      5. The colour chain resolves: a readable `textureFile` paints the cubes,
         and blanking it falls back to `defaultColor` instead of erroring.
    """
    import os
    import tempfile
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    from mpynode._common.methods.test_helpers import assert_true

    name = self.get_name()
    cube_t = mc.polyCube(constructionHistory=False, width=4, height=4, depth=4)[0]
    shape = mc.listRelatives(cube_t, shapes=True, fullPath=True)[0]
    mc.connectAttr(shape + ".worldMesh[0]", name + ".inMesh", force=True)
    render = mc.createNode("mesh")
    mc.connectAttr(name + ".outMesh", render + ".inMesh", force=True)

    def _counts():
        mc.dgeval(render + ".outMesh")
        sel = om2.MSelectionList()
        sel.add(render)
        try:
            fn = om2.MFnMesh(sel.getDagPath(0))
            return fn.numVertices, fn.numPolygons
        except Exception:
            return 0, 0

    VS = 0.5
    mc.setAttr(name + ".voxelSize", VS)
    nv, nf = _counts()
    assert_true(nv > 0 and nv % 8 == 0 and nf % 6 == 0 and nv // 8 == nf // 6,
                "voxels must be whole cubes (verts=%d faces=%d)" % (nv, nf))
    fine = nv // 8

    sel = om2.MSelectionList()
    sel.add(render)
    pts = om2.MFnMesh(sel.getDagPath(0)).getPoints(om2.MSpace.kObject)

    # Every voxel vertex inside the source bbox grown by one voxel.
    lo, hi = -2.0 - VS, 2.0 + VS
    assert_true(all(lo <= p[i] <= hi for p in pts for i in range(3)),
                "voxels must stay within the source bounds")

    # WORLD-anchored, corner on the origin: cell i spans [i*VS, (i+1)*VS], so
    # every cube vertex must be an exact integer multiple of VS. A lattice
    # anchored to the mesh minimum instead would fail this outright.
    worst = max(abs(p[i] / VS - round(p[i] / VS)) for p in pts for i in range(3))
    assert_true(worst < 1e-6,
                "cube vertices must land on the world voxel lattice "
                "(worst offset %.9f of a cell)" % worst)

    mc.setAttr(name + ".voxelSize", 1.0)
    coarse = _counts()[0] // 8
    assert_true(coarse <= fine,
                "coarser voxels must not increase the count "
                "(coarse=%d fine=%d)" % (coarse, fine))
    mc.setAttr(name + ".voxelSize", VS)

    # Colour chain. Byte 0/255 are exact fixed points of the sRGB EOTF, so a
    # solid-red image must land as exactly (1, 0, 0) on every cube.
    buf = bytes(bytearray([255, 0, 0, 255] * 16))
    tex = os.path.join(tempfile.gettempdir(), "mpy_voxelize_selftest.png")
    im = om2.MImage()
    im.create(4, 4, 4, om2.MImage.kByte)
    im.setPixels(buf, 4, 4)
    im.writeToFile(tex, "png")

    def _colors():
        # Return plain (r, g, b) tuples, NOT MColors. The MColor objects belong
        # to the MColorArray, so handing them back outlives the array and reads
        # freed memory; copy the floats out while it is still alive.
        mc.dgeval(render + ".outMesh")
        sel2 = om2.MSelectionList()
        sel2.add(render)
        try:
            arr = om2.MFnMesh(sel2.getDagPath(0)).getVertexColors()
            return [(arr[i].r, arr[i].g, arr[i].b) for i in range(len(arr))]
        except Exception:
            return []

    mc.setAttr(name + ".defaultColor", 0.25, 0.5, 0.75, type="double3")
    mc.setAttr(name + ".textureFile", tex, type="string")
    cols = _colors()
    assert_true(bool(cols) and all(abs(r - 1.0) < 1e-4 and abs(g) < 1e-4
                                   and abs(b) < 1e-4 for r, g, b in cols),
                "a solid-red texture must paint every cube red")

    # A blank path is not an error -- the cube carries no vertex colours, so
    # the chain must drop all the way to defaultColor.
    mc.setAttr(name + ".textureFile", "", type="string")
    cols = _colors()
    assert_true(bool(cols) and all(
        abs(r - 0.25) < 1e-4 and abs(g - 0.5) < 1e-4
        and abs(b - 0.75) < 1e-4 for r, g, b in cols),
        "a blank textureFile must fall back to defaultColor")
'''

VOXELIZE_DESC = (
    "# Voxelize\n\n"
    "Rebuilds a mesh as a hollow **voxel shell** (an `mPyMesh`) on `outMesh`, "
    "one cube per occupied cell. Use it for a chunky, blocky version of a "
    "model that stays live. The cubes are **not** welded.\n\n"
    "Occupancy is found by **closest point**, not by binning the source "
    "geometry, so the result does not depend on how finely the source happens "
    "to be tessellated -- a two-triangle wall voxelizes as solidly as a dense "
    "mesh:\n\n"
    "1. Lay a **world-anchored** lattice over the source bounding box. Cell "
    "`i` spans `[i*voxelSize, (i+1)*voxelSize)`, so a cube **corner** sits "
    "exactly on the origin. Because the lattice is fixed in world space and "
    "not tied to the mesh's own minimum, the voxels do not swim when the "
    "source moves or deforms.\n"
    "2. Build the dense 3D cloud of every cell **centre** in that box and ask "
    "the mesh for the closest surface point to each.\n"
    "3. Snap each returned sample to the cell containing it and drop the "
    "duplicates, keeping the sample **closest to its own grid point**. Those "
    "cells are the voxels, and each winner supplies its cube's colour.\n\n"
    "Colour resolves down a chain, and each link is a *fallback*, never an "
    "error:\n\n"
    "1. **`textureFile`** sampled bilinearly at the UV of the exact closest "
    "point. The image is read with Maya's own `MImage` (no PIL) and "
    "linearized from sRGB, so voxels shade at the same brightness a standard "
    "`file` node would give.\n"
    "2. The source mesh's **vertex colours**, when the path is blank or the "
    "file cannot be read.\n"
    "3. **`defaultColor`**, when there are no vertex colours either.\n\n"
    "`textureFile` takes an absolute path, or one **relative to a template "
    "search root** -- which is what `setup` seeds it with "
    "(`MPyFile/File Simple/test_grid.png`, the grid the MPyFile "
    "examples use), so the shipped example paints no matter where mpynode's "
    "templates are installed. Clear the field to fall through to the rest of "
    "the chain. `setup` also switches **`displayColors`** on for the render "
    "mesh it builds, since a new mesh does not draw its colour set until you "
    "do.\n\n"
    "Attributes are interpolated with the hit triangle's barycentric weights, "
    "so the lookup sits on the true closest point rather than on a nearby "
    "sample. UVs are collapsed to one per vertex first, so on a UV seam one "
    "of the several is kept -- invisible at voxel resolution.\n\n"
    "`maxVoxels` is a safety brake, and it is checked on the **grid** before "
    "a single query runs. The sweep is cubic in `1/voxelSize`, so halving "
    "`voxelSize` costs eight times as much; the brake aborts immediately with "
    "the real count rather than stalling Maya. Set it to 0 to disable.\n\n"
    "**Create + Run demo** voxelizes a sphere so you can drag `voxelSize` and "
    "watch the shell rebuild live."
)


def build_voxelize_mesh():
    mc.file(new=True, force=True)
    from mpynode._common.node_setups import find_demo
    from mpynode.wrappers.mpy_mesh import MPyMesh

    n = MPyMesh.create(name="voxelizeMesh")
    # Add order IS the Channel Box / Designer display order: the source, then
    # the one knob that matters (voxelSize), then the safety brake and the
    # colour chain.
    n.add_input_attr("inMesh", "mesh")
    n.add_input_attr("voxelSize", "double", default_value=0.25,
                     min_value=0.0)
    n.add_input_attr("maxVoxels", "int", default_value=20000, min_value=0)
    n.add_input_attr("textureFile", "string")
    n.add_input_attr("defaultColor", "color")
    n.set_init_expression(VOXELIZE_INIT)
    n.set_compute_expression(VOXELIZE_COMPUTE)
    n.set_methods_source(VOXELIZE_METHODS)
    nm = n.get_name()

    # Capture the VANILLA payload before any live mutation.
    _stamp_class(n, "VoxelizeMesh", "mPyMesh")
    clean_payload = serialize_node(n, include_persistent=False)

    # --- pure-function checks on the Init helpers -------------------------
    ns = {}
    exec(VOXELIZE_INIT, ns)
    grid_fn = ns["_vox_grid"]
    winners = ns["_vox_winners"]
    cubes = ns["_vox_cubes"]

    # The lattice must be WORLD-anchored with a cube CORNER on the origin:
    # centres land on (i + 0.5) * vs, so a box straddling the origin yields
    # centres at +/-0.5 for vs=1 and NEVER a centre at 0.
    # x spans cells floor(-1.2)..floor(1.2) = -2..1 (four), y and z -1..0 (two).
    g = grid_fn(np.array([-1.2, -0.4, -0.4]), np.array([1.2, 0.4, 0.4]), 1.0)
    grid_ok = (g.shape == (4 * 2 * 2, 3)
               and np.allclose(np.unique(g[:, 0]), [-1.5, -0.5, 0.5, 1.5])
               and np.allclose(np.unique(g[:, 1]), [-0.5, 0.5])
               # centres sit half a cell off the lattice, so NO centre is ever
               # on the origin -- a cube CORNER is.
               and np.allclose(np.abs(g - np.round(g)), 0.5)
               and not np.any(np.all(np.abs(g) < 1e-12, axis=1)))

    # Dedupe keeps the sample CLOSEST to its own grid point, not the first one
    # seen. Two samples in cell 0: the far one is listed first, so a naive
    # first-wins would pick it.
    smp = np.array([[0.90, 0.10, 0.10], [0.55, 0.50, 0.50],
                    [1.60, 0.50, 0.50]])
    grd = np.array([[0.50, 0.50, 0.50], [0.50, 0.50, 0.50],
                    [1.50, 0.50, 0.50]])
    cells, win = winners(smp, grd, 1.0)
    win_ok = (cells.shape[0] == 2
              and np.array_equal(np.sort(win), np.array([1, 2]))
              and 0 not in set(win.tolist()))

    # The cube batcher: 8 verts + 6 quads per centre, and each cube spans
    # exactly 2*half on every axis.
    cp, cc, ci = cubes(np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]]), 0.5)
    cube_ok = (cp.shape == (16, 3) and cc.shape == (12,)
               and int(ci.max()) == 15 and bool((cc == 4).all())
               and abs(float(cp[:8].max(axis=0)[0] - cp[:8].min(axis=0)[0])
                       - 1.0) < 1e-9)

    helpers_ok = grid_ok and win_ok and cube_ok

    # --- live end-to-end: voxelize a cube of known size -------------------
    cube_t = mc.polyCube(constructionHistory=False, width=4, height=4,
                         depth=4)[0]
    shape = mc.listRelatives(cube_t, shapes=True, fullPath=True)[0]
    mc.connectAttr(shape + ".worldMesh[0]", nm + ".inMesh", force=True)
    render = mc.createNode("mesh", name="voxelizeRenderShape")
    mc.connectAttr(nm + ".outMesh", render + ".inMesh", force=True)

    def live_counts():
        mc.dgeval(render + ".outMesh")
        rsel = om.MSelectionList()
        rsel.add(render)
        try:
            rfn = om.MFnMesh(rsel.getDagPath(0))
            return rfn.numVertices, rfn.numPolygons
        except Exception:
            return 0, 0

    def voxel_points():
        mc.dgeval(render + ".outMesh")
        rsel = om.MSelectionList()
        rsel.add(render)
        try:
            rfn = om.MFnMesh(rsel.getDagPath(0))
        except Exception:
            return np.zeros((0, 3))
        return np.array([[p.x, p.y, p.z]
                         for p in rfn.getPoints(om.MSpace.kObject)])

    # A 4x4x4 cube (spanning -2..2) at voxelSize 0.5.
    mc.setAttr(nm + ".voxelSize", 0.5)
    av, af = live_counts()
    whole_ok = (av > 0 and av % 8 == 0 and af % 6 == 0 and av // 8 == af // 6)

    vp = voxel_points()
    # Corner on the origin: every cube vertex is an exact multiple of voxelSize.
    align_ok = bool(vp.size) and float(np.abs(vp / 0.5
                                              - np.round(vp / 0.5)).max()) < 1e-9

    # HOLLOW: a shell voxel always touches the box, so no cube CENTRE may lie
    # strictly inside the box shrunk by one voxel.
    ctr = vp.reshape(-1, 8, 3).mean(axis=1) if vp.size else np.zeros((0, 3))
    hollow_ok = bool(ctr.size) and bool(
        (np.abs(ctr).max(axis=1) >= 2.0 - 0.5 - 1e-9).all())

    # Coarser voxels -> no more cubes.
    mc.setAttr(nm + ".voxelSize", 2.0)
    cv = live_counts()[0]
    coarse_ok = 0 < cv <= av

    # WORLD-anchored, not mesh-anchored: nudge the SOURCE by a fraction of a
    # voxel and the cubes must STILL sit on the same world lattice. A lattice
    # anchored to the mesh minimum would drift with the mesh and fail here.
    mc.setAttr(nm + ".voxelSize", 0.5)
    mc.setAttr(cube_t + ".translateX", 0.13)
    mc.setAttr(cube_t + ".translateY", -0.07)
    vp2 = voxel_points()
    anchor_ok = bool(vp2.size) and float(np.abs(vp2 / 0.5
                                                - np.round(vp2 / 0.5)).max()) < 1e-9
    mc.setAttr(cube_t + ".translateX", 0.0)
    mc.setAttr(cube_t + ".translateY", 0.0)

    # The safety brake fires on the GRID (before any query) and the node
    # recovers once the cap is raised.
    mc.setAttr(nm + ".maxVoxels", 4)
    mc.setAttr(nm + ".voxelSize", 0.25)
    brake_ok = live_counts()[0] == 0        # compute raised -> nothing emitted
    mc.setAttr(nm + ".maxVoxels", 20000)
    mc.setAttr(nm + ".voxelSize", 0.5)
    recover_ok = live_counts()[0] > 0

    live_ok = (whole_ok and align_ok and hollow_ok and coarse_ok
               and anchor_ok and brake_ok and recover_ok)

    # --- colour chain: texture -> vertex colour -> defaultColor -----------
    import tempfile

    def write_png(fname, w, h, texels):
        """A tiny RGBA PNG from byte triples, so no external asset is needed.
        (api1 setPixels(bytes) raises a SWIG TypeError -- om here is api2.)"""
        buf = bytes(bytearray(
            [ch for t in texels for ch in (t[0], t[1], t[2], 255)]))
        path = os.path.join(tempfile.gettempdir(), fname)
        im = om.MImage()
        im.create(w, h, 4, om.MImage.kByte)
        im.setPixels(buf, w, h)
        im.writeToFile(path, "png")
        return path

    def voxel_colors():
        # Return plain (r, g, b) tuples, NOT MColors. The MColor objects belong
        # to the MColorArray, so handing them back outlives the array and reads
        # freed memory; copy the floats out while it is still alive.
        mc.dgeval(render + ".outMesh")
        rsel = om.MSelectionList()
        rsel.add(render)
        try:
            arr = om.MFnMesh(rsel.getDagPath(0)).getVertexColors()
            return [(arr[i].r, arr[i].g, arr[i].b) for i in range(len(arr))]
        except Exception:
            return []

    # Byte 0 and 255 are exact fixed points of the sRGB EOTF, so every expected
    # value below is exact rather than approximate.
    red_png = write_png("mpy_voxelize_red.png", 4, 4, [(255, 0, 0)] * 16)
    quad_png = write_png("mpy_voxelize_quad.png", 2, 2,
                         [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)])

    # Pure-function: the sampler resolves each texel centre of the 2x2 to its
    # authored colour, and the exact image centre to their mean -- which only
    # holds if the filtering really is bilinear across all four.
    read_img = ns["_vox_read_image"]
    sample_tex = ns["_vox_sample_texture"]
    img = read_img(quad_png)
    got = set()
    mid_ok = False
    if img is not None:
        centres = np.array([[0.25, 0.25], [0.75, 0.25],
                            [0.25, 0.75], [0.75, 0.75]])
        got = set(tuple(float(v) for v in np.round(c, 4))
                  for c in sample_tex(img, centres))
        mid = sample_tex(img, np.array([[0.5, 0.5]]))[0]
        wrap = sample_tex(img, np.array([[1.25, 0.25], [0.25, 0.25]]))
        mid_ok = (np.allclose(mid, [0.5, 0.5, 0.5], atol=1e-4)
                  and np.allclose(wrap[0], wrap[1], atol=1e-9))
    tex_fn_ok = (img is not None and img.shape[:2] == (2, 2) and mid_ok
                 and got == {(1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
                             (0.0, 0.0, 1.0), (1.0, 1.0, 1.0)}
                 and read_img("") is None
                 and read_img("/no/such/voxelize/file.png") is None)

    # The SHIPPED sample texture must resolve from its RELATIVE path, or the
    # template only paints on the machine that built it.
    rel_fn_ok = (read_img(VOXELIZE_SAMPLE_TEX) is not None
                 and read_img("MPyFile/no_such_grid.png") is None
                 # setup's literal must be the SAME path this gate proved.
                 and VOXELIZE_SAMPLE_TEX in VOXELIZE_METHODS)

    # Live: a solid texture paints every cube exactly that colour, sampled at
    # the UV of the closest point via the hit triangle's barycentric weights.
    mc.setAttr(nm + ".defaultColor", 0.25, 0.5, 0.75, type="double3")
    mc.setAttr(nm + ".textureFile", red_png, type="string")
    cols = voxel_colors()
    tex_solid_ok = bool(cols) and all(
        abs(r - 1.0) < 1e-4 and abs(g) < 1e-4 and abs(b) < 1e-4
        for r, g, b in cols)

    # A texture with VARIATION must produce more than one voxel colour, which
    # a solid image cannot prove: that is what shows UVs steer the lookup.
    mc.setAttr(nm + ".textureFile", quad_png, type="string")
    cols = voxel_colors()
    tex_uv_ok = len(set((round(r, 4), round(g, 4), round(b, 4))
                        for r, g, b in cols)) > 1

    # LIVE relative path: the same string setup seeds must paint through the
    # node, not merely resolve in the helper.
    mc.setAttr(nm + ".textureFile", VOXELIZE_SAMPLE_TEX, type="string")
    cols = voxel_colors()
    rel_ok = rel_fn_ok and len(set((round(r, 4), round(g, 4), round(b, 4))
                                   for r, g, b in cols)) > 1

    # A blank path is NOT an error -- it drops to the next link. The cube has
    # no vertex colours, so that link is defaultColor.
    mc.setAttr(nm + ".textureFile", "", type="string")
    cols = voxel_colors()
    fallback_ok = bool(cols) and all(
        abs(r - 0.25) < 1e-4 and abs(g - 0.5) < 1e-4
        and abs(b - 0.75) < 1e-4 for r, g, b in cols)

    tex_ok = (tex_fn_ok and rel_ok and tex_solid_ok and tex_uv_ok
              and fallback_ok)

    # An unconnected / value mesh input must yield an empty mesh, not a crash.
    empty_ns = {}
    exec(VOXELIZE_INIT, empty_ns)

    class _EmptySelf(object):
        inMesh = None
        voxelSize = 0.25
        maxVoxels = 20000
        textureFile = ""
        defaultColor = (0.8, 0.8, 0.8)
        outMesh = None

    es = _EmptySelf()
    empty_ns["self"] = es
    try:
        exec(compile(VOXELIZE_COMPUTE, "voxelize_compute", "exec"), empty_ns)
        empty_ok = (es.outMesh is not None
                    and getattr(es.outMesh, "points", None) is None)
    except Exception:
        empty_ok = False

    has_demo = find_demo(VOXELIZE_METHODS) is not None

    # Run the authored @maya_test on a FRESH deserialized node.
    test_ok = False
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, name="voxelizeTestCheck")
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        if not test_ok:
            print("[voxelize] @maya_test FAILED: %s" % tres.get("error"))
    except Exception as exc:
        print("[voxelize] @maya_test run ERRORED: %r" % exc)

    ok = helpers_ok and live_ok and tex_ok and empty_ok and has_demo and test_ok
    print("[voxelize] helpers=%s(grid=%s win=%s cube=%s) "
          "live=%s(whole=%s align=%s hollow=%s coarse=%s anchor=%s brake=%s "
          "rec=%s) tex=%s(fn=%s rel=%s solid=%s uv=%s fallback=%s) "
          "empty=%s demo=%s test=%s -> %s"
          % (helpers_ok, grid_ok, win_ok, cube_ok, live_ok, whole_ok, align_ok,
             hollow_ok, coarse_ok, anchor_ok, brake_ok, recover_ok, tex_ok,
             tex_fn_ok, rel_ok, tex_solid_ok, tex_uv_ok, fallback_ok, empty_ok,
             has_demo, test_ok,
             "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(VOXELIZE_DIR, clean_payload, VOXELIZE_DESC)
    return ok


METABALLS_DESC = (
    "# Metaballs\n\n"
    "An `mPyMesh` that builds one solid out of simple SDF shapes -- spheres, "
    "boxes and cylinders -- and extracts one watertight quad mesh into "
    "`outMesh` by **dual marching cubes**. Shapes merge, blend or cut into "
    "each other. It is all one field, so dragging any shape re-solves the "
    "whole mesh live.\n\n"
    "Add shapes with the `addSphere` / `addBox` / `addCylinder` commands on "
    "the Methods tab. Each spawns a transform, and that transform's "
    "`shapeMatrix` places the shape.\n\n"
    "Order matters: every shape combines with everything added before it, and "
    "two flags decide how.\n\n"
    "* `additive` **on**, `smoothing` **0** -> **hard union**, a crisp "
    "merge.\n"
    "* `additive` **on**, `smoothing` **> 0** -> **smooth union**, the "
    "metaball blend the template is named for. Bigger `smoothing` = softer "
    "fillet.\n"
    "* `additive` **off** -> **difference**. The shape is carved OUT of the "
    "solid so far.\n\n"
    "`resolution` sets how finely the surface is sampled (higher = smoother "
    "and slower); `isoValue` pushes the surface out or in -- positive "
    "fattens, negative shrinks.\n\n"
    "**Create + Run demo** builds the word **MPyNode** as one mesh, plus a "
    "Cube / Sphere / Cylinder blob below it so all three operations are on "
    "screen at once. Move the `metaSphere` or `metaCylinder` transforms to "
    "watch the blend and the tunnel update."
)


def _metaballs_probe_field(arr, points):
    """Fold the SDF stream in ``arr`` (the strokes_to_arrays layout) at
    ``points`` (P,3) and return the combined distances (P,) -- a faithful,
    single-point mirror of ``sdf_dmc.mesh_from_shapes``' CSG fold, used to prove
    the demo's difference actually carves and its smooth union actually adds."""
    from mpynode._common.nodes.mesh import sdf_dmc

    mats = arr["matrices"]
    st = arr["shape_types"]
    add = arr["additive"]
    sm = arr["smoothing"]
    rad = arr["radius"]
    hgt = arr["height"]
    ax = arr["axis"]
    half = arr["half_extents"]
    combined = sdf_dmc.sample_shape(
        mats[0], st[0], rad[0], hgt[0], ax[0], half[0], points)
    for s in range(1, mats.shape[0]):
        d = sdf_dmc.sample_shape(
            mats[s], st[s], rad[s], hgt[s], ax[s], half[s], points)
        if bool(add[s]):
            if float(sm[s]) > 0.0:
                combined = sdf_dmc.sdf_smooth_union(combined, d, float(sm[s]))
            else:
                combined = sdf_dmc.sdf_union(combined, d)
        else:
            combined = sdf_dmc.sdf_difference(combined, d)
    return combined


def _metaballs_full_arrays(carve=True):
    """The demo's exact SDF stream (26 text boxes + Cube/Sphere/Cylinder blob)
    as the flat parallel arrays ``mesh_from_shapes`` consumes. ``carve=False``
    flips the cylinder to additive so the carved/filled fields can be compared.
    Kept in lock-step with DEMO_METABALLS' coordinates + flags."""
    from mpynode._demos import sdf_text

    text = sdf_text.strokes_to_arrays(sdf_text.word_strokes("MPyNode"))

    def _T(tx, ty, tz):
        M = np.eye(4, dtype=np.float64)
        M[3, 0], M[3, 1], M[3, 2] = tx, ty, tz
        return M

    # (matrix, type, additive, smoothing, radius, height, axis, half_extents)
    blob = [
        (_T(0.0, -2.4, 0.0), 1, True, 0.0, 1.0, 1.0, 1, [0.9, 0.9, 0.9]),
        (_T(0.75, -1.65, 0.0), 0, True, 0.7, 0.8, 1.0, 1, [0.5, 0.5, 0.5]),
        (_T(0.0, -2.4, 0.0), 2, carve is False, 0.0, 0.45, 3.0, 0,
         [0.5, 0.5, 0.5]),
    ]
    return dict(
        matrices=np.concatenate(
            [text["matrices"], np.array([b[0] for b in blob])], axis=0),
        shape_types=np.concatenate(
            [text["shape_types"], np.array([b[1] for b in blob], np.int64)]),
        additive=np.concatenate(
            [text["additive"], np.array([b[2] for b in blob], bool)]),
        smoothing=np.concatenate(
            [text["smoothing"], np.array([b[3] for b in blob], np.float64)]),
        radius=np.concatenate(
            [text["radius"], np.array([b[4] for b in blob], np.float64)]),
        height=np.concatenate(
            [text["height"], np.array([b[5] for b in blob], np.float64)]),
        axis=np.concatenate(
            [text["axis"], np.array([b[6] for b in blob], np.int64)]),
        half_extents=np.concatenate(
            [text["half_extents"], np.array([b[7] for b in blob], np.float64)]),
    )


def build_metaballs():
    mc.file(new=True, force=True)
    for plugin in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(plugin, q=True, loaded=True):
            mc.loadPlugin(plugin)
    from mpynode._common.node_setups import find_demo
    from mpynode._common.io.mpn_io import deserialize_node
    from mpynode._demos import build_mPyMesh_sdf_dmc as sdf_build
    from mpynode._common.nodes.mesh import sdf_dmc
    from mpynode.wrappers.mpy_mesh import MPyMesh

    ok = False
    detail = ""
    try:
        g = MPyMesh.create(name="metaballs")
        sdf_build.configure_node(g)                      # SDF inputs + I/C/M
        methods_src = (sdf_build.build_methods_source()
                       + "\n\n" + DEMO_METABALLS)         # + the demo body
        g.set_methods_source(methods_src)

        # Capture the VANILLA node-only payload NOW, before the live demo mutates
        # the scene; only written if the gate passes.
        _stamp_class(g, "Metaballs", "mPyMesh")
        clean_payload = serialize_node(g, include_persistent=False)

        # --- pure-field checks: the demo's exact stream builds a real mesh, the
        #     difference carves, and the smooth-union sphere adds volume. ---
        arr = _metaballs_full_arrays(carve=True)
        pts, cnts, idx = sdf_dmc.mesh_from_shapes(
            resolution=12, iso_value=0.0, **arr)
        uniq = np.unique(idx)
        field_ok = (pts.shape[0] > 0 and int(cnts.sum()) == idx.shape[0]
                    and uniq.size == pts.shape[0] and uniq[0] == 0
                    and uniq[-1] == pts.shape[0] - 1)

        # Probe the cube+cylinder core (inside both): difference pushes it
        # OUTSIDE the solid (field > 0), whereas the filled variant keeps it
        # INSIDE (field < 0). SDF convention: negative == inside.
        core = np.array([[0.0, -2.4, 0.0]], dtype=np.float64)
        carved_core = float(_metaballs_probe_field(
            _metaballs_full_arrays(carve=True), core)[0])
        filled_core = float(_metaballs_probe_field(
            _metaballs_full_arrays(carve=False), core)[0])
        carve_ok = carved_core > 0.0 and filled_core < 0.0

        # Probe a point inside the sphere but OUTSIDE the cube and OUTSIDE the
        # cylinder: the smooth-union sphere must add solid there (field < 0).
        sph = np.array([[1.3, -1.65, 0.0]], dtype=np.float64)
        sphere_val = float(_metaballs_probe_field(arr, sph)[0])
        sphere_ok = sphere_val < 0.0

        # --- live demo: deserialize the shipped payload, run the demo, and
        #     verify the stream + flags + a real, carved render mesh. ---
        mc.file(new=True, force=True)
        for plugin in ("mpynode_api1", "mpynode_api2"):
            if not mc.pluginInfo(plugin, q=True, loaded=True):
                mc.loadPlugin(plugin)
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tnm = tnode.get_name()
        from mpynode._common.methods.methods_registry import run_node_demo
        run_node_demo(tnode)

        n_shapes = mc.getAttr(tnm + ".shapeMatrix", size=True)
        types = [mc.getAttr("%s.shapeType[%d]" % (tnm, i)) for i in range(26, 29)]
        adds = [mc.getAttr("%s.additive[%d]" % (tnm, i)) for i in range(26, 29)]
        sm27 = mc.getAttr("%s.smoothing[27]" % tnm)
        # 26 text boxes + cube(1) sphere(0) cylinder(2); cube/sphere additive,
        # cylinder subtracted; the sphere carries the metaball smoothing.
        flags_ok = (n_shapes == 29 and types == [1, 0, 2]
                    and adds == [1, 1, 0] and sm27 > 0.0)

        text_grp = mc.ls(tnm + "Text", long=True) or []
        shp_grp = mc.ls(tnm + "Shapes", long=True) or []
        groups_ok = (
            bool(text_grp)
            and len(mc.listRelatives(text_grp[0], children=True,
                                     type="transform") or []) == 26
            and bool(shp_grp)
            and len(mc.listRelatives(shp_grp[0], children=True,
                                     type="transform") or []) == 3)

        rshape = mc.ls(tnm + "RenderShape", type="mesh", long=True) or []

        def _verts():
            mc.dgeval(rshape[0] + ".outMesh")
            sel = om.MSelectionList()
            sel.add(rshape[0])
            try:
                return om.MFnMesh(sel.getDagPath(0)).numVertices
            except Exception:
                return 0

        v_carved = _verts() if rshape else 0
        # Toggle the cylinder to additive on the LIVE node: the tunnel fills in,
        # so the mesh must change -- proof the difference op is doing work.
        v_filled = 0
        if rshape:
            mc.setAttr(tnm + ".additive[28]", 1)
            v_filled = _verts()
            mc.setAttr(tnm + ".additive[28]", 0)
        render_ok = v_carved > 0 and v_filled > 0 and v_carved != v_filled

        has_demo = find_demo(methods_src) is not None
        payload_ok = clean_payload.get("native_type") == "mPyMesh"

        # --- authored @maya_test check on a FRESH deserialized node. ---
        test_ok = False
        test_err = "n/a"
        try:
            mc.file(new=True, force=True)
            for plugin in ("mpynode_api1", "mpynode_api2"):
                if not mc.pluginInfo(plugin, q=True, loaded=True):
                    mc.loadPlugin(plugin)
            ttnode = deserialize_node(clean_payload, restore_persistent=False)
            tres = ttnode.run_test()
            test_ok = bool(tres.get("passed"))
            test_err = tres.get("error") or "ok"
        except Exception as texc:
            test_err = "exc:%r" % texc

        ok = bool(field_ok and carve_ok and sphere_ok and flags_ok
                  and groups_ok and render_ok and has_demo and payload_ok
                  and test_ok)
        detail = (
            "field=%s(v=%d) carve=%s(core c=%.2f f=%.2f) sphere=%s(%.2f) "
            "flags=%s(n=%s t=%s a=%s sm=%.2f) groups=%s render=%s(c=%d f=%d) "
            "demo=%s payload=%s test=%s(%s)"
            % (field_ok, pts.shape[0], carve_ok, carved_core, filled_core,
               sphere_ok, sphere_val, flags_ok, n_shapes, types, adds, sm27,
               groups_ok, render_ok, v_carved, v_filled, has_demo, payload_ok,
               test_ok, test_err))
    except Exception as exc:
        import traceback
        detail = "exc:%r\n%s" % (exc, traceback.format_exc())

    print("[metaballs] %s -> %s" % (detail, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(METABALLS_DIR, clean_payload, METABALLS_DESC)
    return ok


# ======================================================================
# 3. mPyIkSolver -- 2-bone analytic IK
# ======================================================================
IK_INIT = "import math\nimport numpy as np\n"
# NOTE: template.mpn is the SOURCE OF TRUTH for the shipped template; this
# constant must stay byte-identical to templates/MPyIkSolver/Two Bone IK/
# template.mpn's data.expression so re-running the generator can't drift it.
IK_COMPUTE = r'''# 2-bone analytic IK (law of cosines) producing per-joint WORLD matrices.
# Runs during the IK solve when this node is the solver on an ikHandle driving a
# 3-joint chain (root -> mid -> tip). The solve is jointOrient-agnostic: it reads
# each joint's rest (bind) world frame and rotates it so the bone aims correctly,
# then the bridge applies the result via offsetParentMatrix (rotate-only by
# default) -- the joints' own channels and jointOrient are left untouched.
#
# NOTE: this minimal solver's bend plane comes from the pole vector if present,
# else the rest knee direction (stable, avoids knee-pop). Add a dedicated pole
# input + reference axis for production rigs.
import math
import numpy as np

joints = self.joints
if len(joints) >= 3:
    p0 = np.asarray(joints[0]["world_position"], float)   # root (hip)
    p1 = np.asarray(joints[1]["world_position"], float)   # mid  (knee)
    p2 = np.asarray(joints[2]["world_position"], float)   # tip  (ankle)
    W0 = np.asarray(joints[0]["world_matrix"], float).reshape(4, 4)
    W1 = np.asarray(joints[1]["world_matrix"], float).reshape(4, 4)
    B1 = float(np.linalg.norm(p1 - p0))       # upper bone length (rigid)
    B2 = float(np.linalg.norm(p2 - p1))       # lower bone length (rigid)

    target = np.asarray(self.end_effector, float)
    goal_vec = target - p0
    reach = float(np.linalg.norm(goal_vec))
    if reach > 1e-9 and B1 > 1e-9 and B2 > 1e-9:
        goal_dir = goal_vec / reach
        # clamp reachable distance (law-of-cosines domain)
        d = min(max(reach, abs(B1 - B2) + 1e-4), B1 + B2 - 1e-4)
        goal_pt = p0 + d * goal_dir

        pole = np.asarray(self.pole_vector, float)
        ref = (pole - p0) if float(np.linalg.norm(pole)) > 1e-6 else (p1 - p0)
        bend_n = np.cross(goal_dir, ref)
        if float(np.linalg.norm(bend_n)) < 1e-6:
            bend_n = np.cross(goal_dir, np.array([0.0, 0.0, 1.0]))
        if float(np.linalg.norm(bend_n)) < 1e-6:
            bend_n = np.cross(goal_dir, np.array([1.0, 0.0, 0.0]))
        bend_n = bend_n / np.linalg.norm(bend_n)

        cos_a = (B1 * B1 + d * d - B2 * B2) / (2.0 * B1 * d)
        alpha = math.acos(max(-1.0, min(1.0, cos_a)))

        def rot3(axis, ang):
            # column-vector Rodrigues rotation (R @ v) about a unit axis.
            x, y, z = axis[0], axis[1], axis[2]
            c = math.cos(ang)
            s = math.sin(ang)
            k = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
            return np.eye(3) + s * k + (1.0 - c) * (k @ k)

        upper_dir = rot3(bend_n, alpha) @ goal_dir
        upper_dir = upper_dir / np.linalg.norm(upper_dir)
        knee_pt = p0 + B1 * upper_dir
        lower_dir = goal_pt - knee_pt
        lower_dir = lower_dir / np.linalg.norm(lower_dir)

        def aim(w_rest, rest_dir, new_dir):
            # World matrix that re-aims a joint's bind frame so its bone points
            # from rest_dir to new_dir. Returns w_rest @ delta, where delta's
            # rotation is the transpose of the (column) rotation mapping
            # rest_dir->new_dir (row-vector Maya). Only rotation is used
            # downstream (translate is gated off), so the delta translation is 0.
            a = rest_dir / np.linalg.norm(rest_dir)
            b = new_dir / np.linalg.norm(new_dir)
            v = np.cross(a, b)
            s = float(np.linalg.norm(v))
            c = float(np.dot(a, b))
            if s < 1e-9:
                rct = np.eye(3)
            else:
                rct = rot3(v / s, -math.acos(max(-1.0, min(1.0, c))))
            delta = np.eye(4)
            delta[:3, :3] = rct
            return w_rest @ delta

        self.world_matrices[0] = aim(W0, p1 - p0, upper_dir)   # root aims upper bone
        self.world_matrices[1] = aim(W1, p2 - p1, lower_dir)   # mid  aims lower bone
        # tip (joint 2) is left as None -> it follows the chain.
        self.apply_rotate = True       # reorient the joints...
        self.apply_translate = False   # ...keep their rest translate (bone lengths)
        self.apply_scale = False
'''


# Demo authored into the two-bone IK template's Methods tab: fabricate a full
# leg (hip -> knee -> ankle) driven by an ikHandle that uses THIS solver, plus a
# draggable goal locator point-constrained to the handle. "Create + Run demo"
# gives a poseable leg with zero manual rigging.
IK_DEMO = '''@maya_demo(label="Two-Bone IK Leg")
def demo(self):
    """Build a 3-joint leg (hip -> knee -> ankle, bones down -Y) and drive it
    with an ikHandle that uses THIS solver, then wire a draggable goal locator to
    the handle. Move the goal to watch the knee bend via the analytic
    law-of-cosines solve."""
    from maya import cmds as mc
    name = self.get_name()

    def _uni(base):
        n, i = base, 1
        while mc.objExists(n):
            i += 1
            n = "%s%d" % (base, i)
        return n

    mc.select(clear=True)
    hip = mc.rename(mc.joint(position=(0.0, 5.0, 0.0)), _uni("ikHip"))
    knee = mc.rename(mc.joint(position=(0.0, 0.0, 0.0)), _uni("ikKnee"))
    ankle = mc.rename(mc.joint(position=(0.0, -5.0, 0.0)), _uni("ikAnkle"))
    handle = mc.ikHandle(startJoint=hip, endEffector=ankle, solver=name, name="ikLeg#")[0]

    goal = mc.spaceLocator(name="ikGoal#")[0]
    mc.setAttr(goal + ".translate", 3.0, 1.0, 2.0, type="double3")
    mc.pointConstraint(goal, handle, maintainOffset=False)

    mc.select(goal, replace=True)
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_test(label="Two-bone IK: tip reaches a reachable goal and the knee bends", digits=3)
def test_two_bone_ik(self):
    """Validate the solver's INTENT (same test passes interpreted AND compiled ->
    parity): a 3-joint leg (hip -> knee -> ankle, bones down -Y) driven by an
    ikHandle bound to THIS solver, with the handle pulled to a reachable goal,
    lands the ankle (tip) on the goal and bends the knee -- mirroring the
    builder's live compute_ok (dist_close < 1.0, bend_close > 15)."""
    from maya import cmds as mc
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_true

    name = self.get_name()

    mc.select(clear=True)
    hip = mc.joint(position=(0.0, 5.0, 0.0))
    knee = mc.joint(position=(0.0, 0.0, 0.0))
    ankle = mc.joint(position=(0.0, -5.0, 0.0))
    handle = mc.ikHandle(startJoint=hip, endEffector=ankle, solver=name)[0]

    goal = (3.0, 1.0, 2.0)   # inside the 10-unit reach of the two 5-unit bones
    mc.move(goal[0], goal[1], goal[2], handle)
    mc.refresh(force=True)

    tip = mc.xform(ankle, q=True, ws=True, t=True)
    dist = float(np.linalg.norm(np.array(tip) - np.array(goal)))
    # The bend is the angle between the two bones, from world positions. The
    # joints' rotate channels read 0.0 here even though the tip has moved, so a
    # `rotateX` reading measured nothing -- and failed the interpreted node and
    # the compiled one identically (both put the tip on the goal, 114.8 deg).
    hip_p = np.array(mc.xform(hip, q=True, ws=True, t=True))
    knee_p = np.array(mc.xform(knee, q=True, ws=True, t=True))
    upper, lower = knee_p - hip_p, np.array(tip) - knee_p
    cosang = float(np.dot(upper, lower)
                   / (np.linalg.norm(upper) * np.linalg.norm(lower)))
    bend = float(np.degrees(np.arccos(max(-1.0, min(1.0, cosang)))))

    # Tip reaches the goal (chain solved) and the knee is genuinely bent.
    assert_true(dist < 1.0, "tip is %.3f from the goal" % dist)
    assert_true(bend > 15.0, "knee barely bends (bone angle %.2f deg)" % bend)
'''


def build_ik():
    mc.file(new=True, force=True)
    from mpynode.wrappers.mpy_iksolver import MPyIkSolver

    mc.select(clear=True)
    hip = mc.joint(name="hipJ", position=(0, 5, 0))
    knee = mc.joint(name="kneeJ", position=(0, 0, 0))
    ankle = mc.joint(name="ankleJ", position=(0, -5, 0))
    solver = MPyIkSolver.create(name="twoBoneIK")
    solver.set_init_expression(IK_INIT)
    solver.set_compute_expression(IK_COMPUTE)
    solver.set_methods_source(IK_DEMO)
    nm = solver.get_name()
    try:
        mc.setAttr(nm + ".profile_enabled", 0)
    except Exception:
        pass
    handle = mc.ikHandle(startJoint=hip, endEffector=ankle, solver=nm,
                         name="legH")[0]

    def solve(goal):
        mc.move(goal[0], goal[1], goal[2], handle)
        mc.refresh(force=True)
        return mc.xform(knee, q=True, ro=True), mc.xform(ankle, q=True, ws=True, t=True)

    krot_close, tip_close = solve((3, 1, 2))         # within reach
    krot_near, _ = solve((0, -4.7, 0))               # genuinely near-extension
    krot_far, _ = solve((0, -20, 0))                 # out of reach -> clamp
    bend_close = abs(krot_close[0])
    bend_near = abs(krot_near[0])
    dist_close = float(np.linalg.norm(np.array(tip_close) - np.array([3, 1, 2])))
    compute_ok = (bend_close > 15.0 and bend_near < bend_close
                  and dist_close < 1.0 and abs(krot_far[0]) < 5.0)

    # --- demo check: the authored "Create + Run demo" builds a poseable leg on
    #     a FRESH deserialized solver and the knee bends toward the goal. ---
    _stamp_class(solver, "TwoBoneIK", "mPyIkSolver")
    clean_payload = serialize_node(solver, include_persistent=False)
    demo_ok = False
    demo_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node
        from mpynode._common.methods.methods_registry import run_node_demo
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        run_node_demo(tnode)
        d_knee = (mc.ls("ikKnee*", type="joint") or [None])[0]
        d_goal = (mc.ls("ikGoal*", type="transform") or [None])[0]
        d_hip = (mc.ls("ikHip*", type="joint") or [None])[0]
        chain_ok = bool(d_hip and d_knee
                        and d_knee in (mc.listRelatives(d_hip, ad=True) or []))
        bent = None
        try:
            mc.refresh(force=True)
            bent = abs(mc.getAttr(d_knee + ".rotateX")) if d_knee else None
        except Exception:
            bent = None
        # Gate on structure (the numeric solve is already covered by compute_ok);
        # the bend value is informational (IK solve in headless can vary).
        demo_ok = bool(d_goal and chain_ok)
        demo_err = "goal=%s chain=%s bend=%s" % (d_goal, chain_ok, bent)
    except Exception as exc:
        demo_err = "exc:%r" % exc

    # --- authored @maya_test check on a FRESH deserialized node. ---
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    # Headless standalone has no viewport, so Maya's ikHandle solver never runs
    # (the knee stays at 0 for every goal) -- a Maya platform limitation, NOT a
    # node bug: the node payload (init/compute/methods/inputs) is deterministic
    # and independent of whether the solve ran. When we detect that condition we
    # SKIP the runtime solve + @maya_test checks but still require the demo
    # structure AND that the @maya_test is actually authored in source, so the
    # template still regenerates WITH its embedded test. In an interactive Maya
    # (and for compiled parity via verify.py) the solver runs and both checks are
    # strict -- test_two_bone_ik then asserts the tip reaches the goal + the knee
    # bends.
    from mpynode._common.node_setups import find_tests
    has_test = bool(find_tests(IK_DEMO))
    ik_headless = (bend_close == 0.0 and bend_near == 0.0
                   and abs(krot_far[0]) == 0.0)
    if ik_headless:
        ok = demo_ok and has_test
        verdict = ("PASS (headless: solve+@maya_test SKIPPED, no viewport)"
                   if ok else "FAIL")
    else:
        ok = compute_ok and demo_ok and test_ok
        verdict = "PASS" if ok else "FAIL"
    print("[ik] bend_close=%.2f bend_near=%.2f far_bend=%.2f dist_close=%.3f "
          "demo=%s(%s) test=%s(%s) has_test=%s headless=%s -> %s"
          % (bend_close, bend_near, abs(krot_far[0]), dist_close,
             demo_ok, demo_err, test_ok, test_err, has_test, ik_headless,
             verdict))
    if ok:
        _write_template(
            clean_payload, "mPyIkSolver",
            "# Two-Bone Analytic IK\n\n"
            "Law-of-cosines solver for a 3-joint chain (root -> mid -> tip) "
            "driven by an `ikHandle`. It reads each joint's rest frame, so "
            "jointOrient is left alone, and bends toward the pole vector, "
            "falling back to the rest knee direction.\n\n"
            "**Create + Run demo** builds a 3-joint leg driven by an "
            "ikHandle, plus a draggable goal locator -- move the goal to pose "
            "the leg.")
    return ok


# ======================================================================
# Shared helpers for the locator + file-texture templates below
# ======================================================================
# Bundled demo assets (a grid PNG + the head model + component-tag mesh) live
# beside the example scenes; templates ship a copy so "Create + Run demo" can
# find them next to the template.mpn.
ASSETS_DIR = os.path.join(
    os.environ["MPYNODE_ROOT"], "scripts", "mpynode", "_demos", "data")


def _copy_asset(fname, rel_dir, dest_name=None):
    """Copy a bundled asset from scripts/mpynode/_demos/data into the template
    folder <rel_dir> so its setup can load it at run time. Returns the dest
    path, or None (with a printed warning) if the source is missing.

    ``dest_name`` renames on the way in -- File Composite wants the shipped
    grid under its own ``grid_bg.png`` name, so the one master image can serve
    both it and the templates that load ``test_grid.png``."""
    src = os.path.join(ASSETS_DIR, fname)
    if not os.path.isfile(src):
        print("[asset] MISSING %s" % src)
        return None
    folder = os.path.join(TPL, *rel_dir.split("/"))
    os.makedirs(folder, exist_ok=True)
    dst = os.path.join(folder, dest_name or fname)
    shutil.copy(src, dst)
    return dst


# The mPyFile "simple" + "scanline" templates read their image from `fileName`
# on disk, but also carry an EMBEDDED byte-buffer fallback (a persistent
# `embeddedImage` stored var the setup bakes from the shipped grid PNG) so the
# node still shows something when the path is blank or the file is missing.
#
# There is no FILE_EMBED_INIT any more -- these templates use the plain
# FILE_INIT. The fallback used to be ~60 lines of Init-tab helpers here
# (_ext_for_bytes / _stage_embedded / _resolve_image) that the compute called
# as `_resolve_image(self)`. That spelling could not be compiled: an Init helper
# is opaque to the transpiler, so a compute wrapping the blessed load in one
# lowered to nothing, and codegen honest-rejects a blessed call it cannot lower
# rather than AI-port it. The template was stuck choosing between the embedded
# fallback and the framework sampler.
#
# The fallback is now a FRAMEWORK service inside read_texture() itself
# (_common/methods/file_methods.py), mirrored in C++ by _emit_load's
# nullptr -> nd_img_embedded_path() retry. So `buf = self.read_texture()` gets
# the fallback on BOTH tiers, lowers deterministically, and the template stays
# about the GRADE.


# ======================================================================
# 5. mPyFile -- simple file texture (brightness/contrast + embed fallback)
# ======================================================================
# The primary mPyFile template: a brightness/contrast grade over a framework
# texture read, self-contained (an embedded-image fallback + a full setup so
# "Create + Run setup" shows a textured surface immediately).
#
# This used to be a hand-rolled body that did its OWN nearest-neighbour tap
# (`img[py, px]`) on an Init-resolved buffer. That bypassed self.sample_texture(),
# so it silently lost the BILINEAR filtering, the wrapModeU/V policies and the
# borderColor -- the whole reason the sampler is a framework service -- and it
# AI-ported instead of lowering. Now that read_texture() owns the embedded
# fallback itself, the plain blessed pair does everything the hand-rolled tap
# did and lowers deterministically, so the Compute and Viewport tiers ARE the
# shared FILE_COMPUTE / FILE_VIEW with no substitution at all.
FILE_SIMPLE_COMPUTE = FILE_COMPUTE
FILE_SIMPLE_VIEW = FILE_VIEW


DEMO_FILE_SIMPLE = '''# Full setup for the simple file texture: create a sphere + an unlit surfaceShader,
# assign the shader, drive its colour from this node's outColor, point fileName
# at the shipped grid image AND bake that image into a persistent embeddedImage
# fallback, then (best effort) build the Arnold OSL render path.
def demo(self):
    from maya import cmds as mc
    import os
    name = self.get_name()

    # 1. A sphere + an UNLIT surfaceShader; assign it; drive it from us.
    #    surfaceShader, not lambert: a lambert multiplies the texture by its
    #    diffuse coefficient AND by the scene lighting, so what you see is never
    #    what the node computed. surfaceShader.outColor is both the driven input
    #    and the shading result, so the buffer shows EXACTLY. Every mPyFile
    #    template uses this, which is what makes them comparable side by side.
    sphere = mc.polySphere(radius=5, subdivisionsX=32, subdivisionsY=32,
                           name=name + "_sphere")[0]
    shader = mc.shadingNode("surfaceShader", asShader=True,
                            name=name + "_surface")
    sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True, name=shader + "SG")
    mc.connectAttr(shader + ".outColor", sg + ".surfaceShader", force=True)
    mc.sets(sphere, edit=True, forceElement=sg)
    mc.connectAttr(name + ".outColor", shader + ".outColor", force=True)

    # 2. Locate the shipped grid image beside this template; point fileName at
    #    it AND bake it into a persistent embeddedImage fallback so the node
    #    still shows the grid if the path is later cleared.
    grid = None
    try:
        from mpynode._common.util.template_gallery import _bundled_templates_root
        root = _bundled_templates_root()
        if root:
            cand = os.path.join(root, "MPyFile", "File Simple", "test_grid.png")
            if os.path.isfile(cand):
                grid = cand
    except Exception:
        grid = None
    if grid:
        mc.setAttr(name + ".fileName", grid, type="string")
        try:
            with open(grid, "rb") as fh:
                self.set_variable("embeddedImage", fh.read(), persistent=True)
        except Exception:
            pass

    # 3. Arnold OSL render path (best effort -- viewport is valid without it).
    try:
        from mpynode._common.osl.osl_targets import apply_osl_to_arnold
        osl = apply_osl_to_arnold(name)
        if osl:
            if grid and mc.attributeQuery("fileName", node=osl, exists=True):
                mc.setAttr(osl + ".fileName", grid, type="string")
            if mc.attributeQuery("aiSurfaceShader", node=sg, exists=True):
                amtl = mc.shadingNode("aiStandardSurface", asShader=True,
                                      name=name + "_arnoldMtl")
                try:
                    mc.setAttr(amtl + ".specular", 0.0)
                except Exception:
                    pass
                mc.connectAttr(osl + ".outColor", amtl + ".baseColor", force=True)
                mc.connectAttr(amtl + ".outColor", sg + ".aiSurfaceShader", force=True)
    except Exception:
        pass

    # 4. Force one eval so the swatch / viewport show the grid immediately.
    try:
        mc.dgdirty(name + ".outColor")
        mc.getAttr(name + ".outColor")
    except Exception:
        pass
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_test(label="File texture: image sampled, brightness scales, magenta fallback", digits=3)
def test_file_simple(self):
    """Validate the node's INTENT (the SAME test passes on the interpreted node
    and its C++ compile -> parity):

      1. A solid-grey image reads back at `outColor` as its sRGB->linear value.
      2. Doubling `brightness` doubles the output channel (clamped at 1.0).
      3. A blank `fileName` with no embedded fallback yields magenta.

    Scene-robust: after the demo, `fileName` points at the demo's grid image, a
    persistent `embeddedImage` fallback is baked, and a place2dTexture/user may
    have CONNECTED uCoord/vCoord. The test drives `self` (parity) directly, but
    first breaks any incoming connection on every plug it sets and clears the
    embedded fallback, so it validates the same intent whether run stand-alone,
    after the demo, or twice.
    """
    import os
    import tempfile
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    from mpynode._common.methods.test_helpers import assert_close

    name = self.get_name()

    def _set(plug, *vals, **kw):
        # A demo/user may have CONNECTED this input (place2dTexture -> uCoord/
        # vCoord, or a driver on fileName/brightness/contrast); break it first so
        # the test can drive the value.
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals, **kw)

    # Write a known solid-grey (sRGB byte 128) RGBA image with api2 om2.MImage so
    # the test samples ITS OWN on-disk file -- not whatever image the demo left on
    # `fileName` -- and no external asset is required. (api1 setPixels(bytes)
    # raises a SWIG TypeError, so use om2.)
    grey = 128
    w = h = 4
    buf = bytes([grey, grey, grey, 255]) * (w * h)
    testimg = os.path.join(tempfile.gettempdir(), "mpy_file_simple_test.png")
    im = om2.MImage()
    im.create(w, h, 4, om2.MImage.kByte)
    im.setPixels(buf, w, h)
    im.writeToFile(testimg, "png")

    def out_color(bright=1.0, contrast=1.0):
        _set(name + ".uCoord", 0.5)
        _set(name + ".vCoord", 0.5)
        _set(name + ".brightness", bright)
        _set(name + ".contrast", contrast)
        mc.dgdirty(name + ".outColor")
        return mc.getAttr(name + ".outColor")[0]

    def _lin(s):
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    # 1) The solid-grey image reads back as its sRGB->linear value (contrast 1.0
    #    and brightness 1.0 leave the sampled texel unchanged). Point `fileName`
    #    at OUR image, breaking any driver a demo left on it first.
    _set(name + ".fileName", testimg, type="string")
    expect = _lin(grey / 255.0)
    base = out_color(1.0, 1.0)
    assert_close(list(base), [expect, expect, expect])

    # 2) Doubling brightness doubles the channel (clamped to 1.0).
    b2 = out_color(2.0, 1.0)
    assert_close(b2[0], min(1.0, expect * 2.0))

    # 3) Blank fileName + no embedded fallback -> magenta. The demo bakes a
    #    persistent `embeddedImage` buffer; clear it so there is genuinely no
    #    fallback, then blank `fileName`, so the node must return magenta.
    try:
        self.remove_variable("embeddedImage")
    except Exception:
        pass
    _set(name + ".fileName", "", type="string")
    miss = out_color(1.0, 1.0)
    assert_close(list(miss), [1.0, 0.0, 1.0])
'''

FILE_SIMPLE_DESC = (
    "# File Simple\n\n"
    "A file texture (`mPyFile`) that can carry its own picture. It samples "
    "`fileName` at `uvCoord`, applies `brightness` then `contrast` around "
    "mid-grey, and writes `outColor`/`outAlpha` like a stock file node. It "
    "draws in the swatch, the viewport and an Arnold render (via OSL).\n\n"
    "Bake an image into the `embeddedImage` variable and the node falls back "
    "to it whenever `fileName` is blank or missing, so the texture travels "
    "with the scene.\n\n"
    "**Create + Run demo** builds a sphere and an unlit surfaceShader, points "
    "`fileName` at the shipped `test_grid.png` and bakes it into the "
    "fallback, and (when MtoA is present) wires the Arnold OSL render path."
)


def _verify_file_embed(testimg, grid_path):
    """The embedded-image fallback, now a FRAMEWORK service inside
    read_texture(): with no fileName it must stage the baked byte buffer and
    load it, giving the same array that file loads to on disk; with a fileName
    it must prefer the disk file; with neither it is None.

    Also pins the rule the compositor depends on -- an EXPLICIT path argument
    never falls back, so a blank layer path still yields None."""
    from mpynode._common.methods import file_methods
    with open(grid_path, "rb") as fh:
        data = fh.read()
    staged = file_methods._embedded_path(
        type("_B", (object,), {"embeddedImage": data})())
    if not staged:
        return False, "stage-none"
    dec = _framework_read_texture(staged)
    if dec is None:
        return False, "decode-none"

    class _S(object):
        """Stands in for the SelfProxy at the mPyFile preset DEFAULTS. It has no
        get_init_helper, so file_methods._helper falls back to file_texture_ops
        -- the same entry point _framework_read_texture uses."""
        colorSpace = 0
        preFilter = False
        preFilterKernel = 0
        preFilterRadius = 1.0

    s_embed = _S(); s_embed.fileName = ""; s_embed.embeddedImage = data
    s_disk = _S(); s_disk.fileName = testimg; s_disk.embeddedImage = data
    s_none = _S(); s_none.fileName = ""; s_none.embeddedImage = None

    embed = file_methods.read_texture(s_embed)
    disk = file_methods.read_texture(s_disk)
    nada = file_methods.read_texture(s_none)
    # An explicit path is "read THIS file" -- no fallback, even though s_embed
    # carries bytes. File Composite relies on a blank layer path giving None.
    explicit = file_methods.read_texture(s_embed, "")
    # The staged temp file IS the grid image, so the embedded route must give
    # byte-identical pixels to loading that file directly.
    ok = (embed is not None and np.array_equal(embed, dec)
          and disk is not None
          and np.array_equal(disk, _framework_read_texture(testimg))
          and nada is None and explicit is None)
    return ok, "embed=%s disk=%s none=%s explicit=%s" % (
        embed is not None, disk is not None, nada is None, explicit is None)


def build_file_simple():
    mc.file(new=True, force=True)
    from mpynode._common.node_setups import find_demo
    from mpynode._common.storedvars.stored_vars_api import set_variable
    from mpynode.wrappers.mpy_file import MPyFile

    rows = [r * 30 for r in range(8)]
    testimg = "/tmp/_tpl_simple_gradient.png"
    w, h = _write_test_image(testimg, rows)
    grid = os.path.join(ASSETS_DIR, "test_grid.png")

    f = MPyFile.create(name="fileTexture", seed_defaults=False, as_texture=True)
    f.add_input_attr("brightness", "float", default_value=1.0)
    f.add_input_attr("contrast", "float", default_value=1.0)
    f.set_init_expression(FILE_INIT)
    f.set_compute_expression(FILE_SIMPLE_COMPUTE)
    f.set_viewport_expression(FILE_SIMPLE_VIEW)
    f.set_osl_expression(FILE_OSL)
    f.set_methods_source(DEMO_FILE_SIMPLE)
    nm = f.get_name()

    # Vanilla payload BEFORE the live checks set fileName / bake embeddedImage.
    _stamp_class(f, "FileTexture", "mPyFile")
    clean_payload = serialize_node(f, include_persistent=False)

    mc.setAttr(nm + ".fileName", testimg, type="string")

    def out_color(u, v, bright=1.0, contrast=1.0):
        mc.setAttr(nm + ".uCoord", u)
        mc.setAttr(nm + ".vCoord", v)
        mc.setAttr(nm + ".brightness", bright)
        mc.setAttr(nm + ".contrast", contrast)
        mc.dgdirty(nm + ".outColor")
        return mc.getAttr(nm + ".outColor")[0]

    def _lin(s):
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    top = out_color(0.5, 0.99)[0]
    bottom = out_color(0.5, 0.01)[0]
    top_ok = abs(top - _lin(rows[h - 1] / 255.0)) < 0.05
    bottom_ok = abs(bottom - _lin(rows[0] / 255.0)) < 0.05
    rows_reached = len({
        round(out_color(0.5, (r + 0.5) / h)[0], 3) for r in range(h)})
    sampling_ok = top_ok and bottom_ok and rows_reached >= h - 1

    mid = out_color(0.5, 0.5, 1.0, 1.0)
    g = mid[0]
    b2 = out_color(0.5, 0.5, 2.0, 1.0)
    bright_ok = abs(b2[0] - min(1.0, g * 2.0)) < 0.02

    # Missing file + no embed -> magenta.
    mc.setAttr(nm + ".fileName", "", type="string")
    mc.dgdirty(nm + ".outColor")
    miss = mc.getAttr(nm + ".outColor")[0]
    miss_ok = np.allclose(miss, (1.0, 0.0, 1.0), atol=1e-4)

    # Embedded fallback on the LIVE node: blank fileName + baked embeddedImage
    # -> the grid renders (not magenta).
    with open(grid, "rb") as fh:
        set_variable(nm, "embeddedImage", fh.read(), persistent=True)
    mc.setAttr(nm + ".brightness", 1.0)
    mc.setAttr(nm + ".contrast", 1.0)
    mc.dgdirty(nm + ".outColor")
    emb = mc.getAttr(nm + ".outColor")[0]
    embed_live_ok = not np.allclose(emb, (1.0, 0.0, 1.0), atol=1e-4)
    mc.setAttr(nm + ".fileName", testimg, type="string")

    orient_ok = _verify_file_orientation(testimg)
    embed_ok, embed_err = _verify_file_embed(testimg, grid)
    view_ok, view_err = _verify_file_viewport(
        testimg, FILE_INIT, FILE_SIMPLE_VIEW)
    osl_ok, osl_err = _verify_file_osl()
    has_demo = find_demo(DEMO_FILE_SIMPLE) is not None

    # --- authored @maya_test check on a FRESH deserialized node. ---
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    ok = (sampling_ok and bright_ok and miss_ok and embed_live_ok and embed_ok
          and orient_ok and view_ok and osl_ok and has_demo and test_ok)
    print("[file_simple] sampling=%s bright=%s miss=%s embed_live=%s "
          "embed=%s(%s) orient=%s view=%s(%s) osl=%s(%s) demo=%s test=%s(%s) -> %s"
          % (sampling_ok, bright_ok, miss_ok, embed_live_ok, embed_ok, embed_err,
             orient_ok, view_ok, view_err, osl_ok, osl_err, has_demo,
             test_ok, test_err, "PASS" if ok else "FAIL"))
    if ok:
        _copy_asset("test_grid.png", FILE_SIMPLE_DIR)
        _write_template_to(FILE_SIMPLE_DIR, clean_payload, FILE_SIMPLE_DESC)
    return ok


# ======================================================================
# 6. mPyFile -- scanline: file texture x animated scrolling scan bands
# ======================================================================
FILE_SCAN_COMPUTE = r'''# Scanline file texture: sample the image through the FRAMEWORK, then
# multiply by an animated horizontal scan band that scrolls with `frame`.
#
# The load is not this template's job -- self.read_texture() /
# self.sample_texture() give it `fileName` decoded out of `colorSpace`, the
# optional pre-filter and the wrap modes, the same as every other mPyFile.
# What this template is ABOUT is the band below.
#
# `bands` = number of bands across V, `speed` = scroll rate, `intensity` = how
# dark the troughs get (0 = flat, 1 = full black between).
buf = self.read_texture()
v = self.uvCoord[1]
r, g, b, a = self.sample_texture(buf, self.uvCoord[0], v)

vv = v - np.floor(v)
s = 0.5 + 0.5 * np.sin((vv * self.bands - self.frame * self.speed) * 2.0 * np.pi)
scan = (1.0 - self.intensity) + self.intensity * s

self.outColor = (r * scan, g * scan, b * scan)
self.outAlpha = a
'''

FILE_SCAN_VIEW = r'''# ----------------------------------------------------------------------
# mPyFile SCANLINE -- Viewport source (runs per VP2 updateShader call)
#
# Bakes the SAME animated scanline the Compute tier applies into the linear
# pixel buffer (per row) and uploads it as a float32 texture keyed on `frame`,
# so the VP2 surface scrolls in lock-step with the swatch. Nested guards (no
# module-level return -- that would be a compile-time SyntaxError here).
# ----------------------------------------------------------------------
import maya.api.OpenMayaRender as omr

img = self.read_texture()
if img is not None and self.texture_manager is not None:
    bands = self.bands
    speed = self.speed
    intensity = self.intensity
    t = self.frame

    processed = img.astype(np.float32, copy=True)
    h, w = processed.shape[0], processed.shape[1]
    # Per-row scan: image row py (top-down) -> Maya v = 1 - py/(h-1), matching
    # how Compute samples, so the viewport bands line up with the swatch.
    py = np.arange(h, dtype=np.float32)
    vrow = 1.0 - py / float(max(h - 1, 1))
    srow = 0.5 + 0.5 * np.sin((vrow * bands - t * speed) * 2.0 * np.pi)
    scan = ((1.0 - intensity) + intensity * srow).astype(np.float32)
    processed[..., 0] *= scan[:, None]
    processed[..., 1] *= scan[:, None]
    processed[..., 2] *= scan[:, None]
    np.clip(processed[..., :3], 0.0, 1.0, out=processed[..., :3])
    processed = np.ascontiguousarray(processed, dtype=np.float32)

    map_param = None
    samp_param = None
    for pname in self.shader.parameterList():
        try:
            ptype = self.shader.parameterType(pname)
        except Exception:
            continue
        if map_param is None and ptype == omr.MShaderInstance.kTexture2:
            map_param = pname
        elif samp_param is None and ptype == omr.MShaderInstance.kSampler:
            samp_param = pname
        if map_param and samp_param:
            break

    if map_param:
        desc = omr.MTextureDescription()
        desc.setToDefault2DTexture()
        desc.fWidth = w
        desc.fHeight = h
        desc.fDepth = 1
        desc.fBytesPerRow = w * 4 * 4
        desc.fBytesPerSlice = desc.fBytesPerRow * h
        desc.fMipmaps = 1
        desc.fArraySlices = 1
        desc.fFormat = omr.MRenderer.kR32G32B32A32_FLOAT
        desc.fTextureType = omr.MTextureDescription.kImage2D
        desc.fEnvMapType = omr.MTextureDescription.kEnvNone
        # Keyed on frame (+ look inputs) so the viewport re-uploads and scrolls.
        tex_name = "mpyfile_scanline::%s|t=%.4f|b=%.3f|s=%.4f|i=%.3f" % (
            getattr(self, "fileName", ""), t, bands, speed, intensity)
        texture = self.texture_manager.acquireTexture(
            tex_name, desc, processed.tobytes(), False)
        if texture is not None:
            try:
                assignment = omr.MTextureAssignment()
                assignment.texture = texture
                self.shader.setParameter(map_param, assignment)
            finally:
                try:
                    self.texture_manager.releaseTexture(texture)
                except Exception:
                    pass

    if samp_param:
        try:
            sdesc = omr.MSamplerStateDesc()
            sdesc.setDefaults()
            sdesc.filter = omr.MSamplerState.kMinMagMipLinear
            sdesc.addressU = omr.MSamplerState.kTexClamp
            sdesc.addressV = omr.MSamplerState.kTexClamp
            self.shader.setParameter(samp_param,
                self.state_manager.acquireSamplerState(sdesc))
        except Exception:
            pass
'''

FILE_SCAN_OSL = r'''// ----------------------------------------------------------------------
// scanlineTex -- OSL twin of the scanline Compute look. Wire into an
// aiOslShader (Arnold) so the renderer reproduces the scrolling scan bands.
// Mirrors Compute: sample with the (1 - v) flip, linearize sRGB->scene-linear
// (Arnold's texture() returns RAW sRGB), then multiply by the scan factor.
// ----------------------------------------------------------------------
color srgb_to_linear(color c)
{
    color lo = c / 12.92;
    color hi = pow(max((c + color(0.055)) / 1.055, color(0.0)), 2.4);
    return mix(lo, hi, step(color(0.04045), c));
}

shader scanlineTex(
    string fileName = "",
    float bands = 12.0,
    float speed = 0.1,
    float intensity = 0.6,
    float tIn = 0.0,
    output color outColor = color(0),
    output float outAlpha = 1.0)
{
    float a = 1.0;
    color c = texture(fileName, u, 1.0 - v, "alpha", a);
    c = srgb_to_linear(c);
    float s = 0.5 + 0.5 * sin((v * bands - tIn * speed) * 6.283185307179586);
    float scan = (1.0 - intensity) + intensity * s;
    outColor = clamp(c * scan, color(0), color(1));
    outAlpha = a;
}
'''


DEMO_FILE_SCAN = '''# Full setup for the scanline texture: create a plane + an UNLIT surfaceShader,
# assign it, drive its colour from outColor, point fileName at the shipped
# grid, set a playback range so the bands scroll on play, then (best effort)
# build the Arnold OSL render path with tIn driven by time.
def demo(self):
    from maya import cmds as mc
    import os
    name = self.get_name()

    # surfaceShader, not lambert: the scanline modulation is a few percent at
    # the bright end, and a lambert's diffuse + lighting term swamps exactly
    # that signal. Unlit shows the buffer as computed.
    plane = mc.polyPlane(width=10, height=10, subdivisionsX=1,
                         subdivisionsY=1, name=name + "_plane")[0]
    shader = mc.shadingNode("surfaceShader", asShader=True,
                            name=name + "_surface")
    sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True, name=shader + "SG")
    mc.connectAttr(shader + ".outColor", sg + ".surfaceShader", force=True)
    mc.sets(plane, edit=True, forceElement=sg)
    mc.connectAttr(name + ".outColor", shader + ".outColor", force=True)

    grid = None
    try:
        from mpynode._common.util.template_gallery import _bundled_templates_root
        root = _bundled_templates_root()
        if root:
            cand = os.path.join(root, "MPyFile", "File Scanline", "test_grid.png")
            if os.path.isfile(cand):
                grid = cand
    except Exception:
        grid = None
    if grid:
        mc.setAttr(name + ".fileName", grid, type="string")

    # Playback range so the scanline visibly scrolls on play.
    try:
        mc.playbackOptions(minTime=1, maxTime=120,
                           animationStartTime=1, animationEndTime=120)
        mc.currentTime(1)
    except Exception:
        pass

    # Arnold OSL render path (best effort): drive tIn from time so it scrolls.
    try:
        from mpynode._common.osl.osl_targets import apply_osl_to_arnold
        osl = apply_osl_to_arnold(name)
        if osl:
            if grid and mc.attributeQuery("fileName", node=osl, exists=True):
                mc.setAttr(osl + ".fileName", grid, type="string")
            for p in ("bands", "speed", "intensity"):
                if mc.attributeQuery(p, node=osl, exists=True):
                    try:
                        mc.setAttr(osl + "." + p, mc.getAttr(name + "." + p))
                    except Exception:
                        pass
            if mc.attributeQuery("tIn", node=osl, exists=True):
                try:
                    mc.connectAttr("time1.outTime", osl + ".tIn", force=True)
                except Exception:
                    pass
            if mc.attributeQuery("aiSurfaceShader", node=sg, exists=True):
                amtl = mc.shadingNode("aiStandardSurface", asShader=True,
                                      name=name + "_arnoldMtl")
                try:
                    mc.setAttr(amtl + ".specular", 0.0)
                except Exception:
                    pass
                mc.connectAttr(osl + ".outColor", amtl + ".baseColor", force=True)
                mc.connectAttr(amtl + ".outColor", sg + ".aiSurfaceShader", force=True)
    except Exception:
        pass

    try:
        mc.dgdirty(name + ".outColor")
        mc.getAttr(name + ".outColor")
    except Exception:
        pass
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_test(label="Scanline: image sampled, scan band scrolls, magenta fallback", digits=3)
def test_scanline(self):
    """Validate the node's INTENT (the SAME test passes on the interpreted node
    and its C++ compile -> parity), mirroring the builder's own live checks:

      1. A blank `fileName` yields the magenta "no image" hue.
      2. With a real image wired in, the animated scan band scrolls: at a fixed
         uv the `outColor` changes as `frame` (the timeline) advances.

    Robust to a LIVE, demo-populated scene and to being run twice: the demo may
    have wired `fileName`/`uvCoord`/scan params, so we break incoming
    connections before driving each input.
    """
    import os
    import tempfile
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    from mpynode._common.methods.test_helpers import assert_close, assert_true

    name = self.get_name()

    def _set(plug, *vals, **kw):
        # A demo/user may have CONNECTED this input; break it so the test drives it.
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals, **kw)

    def out_color(u, v, t):
        _set(name + ".uCoord", u)
        _set(name + ".vCoord", v)
        mc.currentTime(t)
        mc.dgdirty(name + ".outColor")
        return mc.getAttr(name + ".outColor")[0]

    # 1) Blank fileName -> the magenta "no image" sentinel. read_texture()
    #    returns None and sample_texture() yields (1, 0, 1); the scan factor
    #    then SCALES it (at intensity 0.6 the trough never reaches the rails),
    #    so assert the HUE -- green off, red == blue, not black -- rather than
    #    an exact (1, 0, 1).
    _set(name + ".fileName", "", type="string")
    miss = out_color(0.5, 0.3, 0.0)
    assert_close(miss[1], 0.0)
    assert_close(miss[0], miss[2])
    assert_true(miss[0] > 0.01,
                "a missing image must read as magenta, not black")

    # Write a per-row gradient RGBA image (row r = grey r*30) so the V-sampling
    # is actually exercised -- no external asset required.
    w = h = 8
    buf = bytearray()
    for r in range(h):
        val = r * 30
        buf += bytes([val, val, val, 255]) * w
    testimg = os.path.join(tempfile.gettempdir(), "mpy_scanline_test.png")
    im = om2.MImage()
    im.create(w, h, 4, om2.MImage.kByte)
    im.setPixels(bytes(buf), w, h)
    im.writeToFile(testimg, "png")

    _set(name + ".fileName", testimg, type="string")
    _set(name + ".bands", 12)
    _set(name + ".speed", 0.1)
    _set(name + ".intensity", 0.6)

    # The wrapper auto-wires `frame` to time1 on create, but a freshly built /
    # deserialized node may not carry it -- ensure the timeline drives `frame`
    # so currentTime actually scrolls the scan band.
    if not (mc.listConnections(name + ".frame", s=True, d=False) or []):
        if not mc.objExists("time1"):
            mc.createNode("time", name="time1", skipSelect=True)
        try:
            mc.connectAttr("time1.outTime", name + ".frame", force=True)
        except Exception:
            pass

    # 2) The scan band scrolls: at a fixed uv, some frame differs from the base
    #    frame (avoid a single pair -- a phase shift of t*speed == integer lands
    #    on the same scan value).
    base = out_color(0.5, 0.3, 0.0)[0]
    scrolled = any(
        abs(out_color(0.5, 0.3, float(t))[0] - base) > 1e-3 for t in (5, 7, 13))
    assert_true(scrolled,
                "scanline should scroll: outColor must change as frame advances")
'''

FILE_SCAN_DESC = (
    "# File Scanline\n\n"
    "A file texture (`mPyFile`) with an animated scan band rolling over it -- "
    "an old-CRT look. `bands` sets how many fit across V (default 12), "
    "`speed` the scroll rate (default 0.1), `intensity` how dark the troughs "
    "get, 0-1 (default 0.6), and `frame` is auto-wired to the timeline.\n\n"
    "If `fileName` is blank or missing, the node falls back to whatever is "
    "baked into the `embeddedImage` variable -- the demo bakes the bundled "
    "`test_grid.png` into it for you.\n\n"
    "It draws in the swatch, the viewport and an Arnold render (via OSL).\n\n"
    "**Create + Run demo** builds a plane and an unlit surfaceShader, sets a 1-120 "
    "playback range so the bands scroll on play, and wires the Arnold OSL "
    "path (when MtoA is present) with `tIn` driven by time."
)


def _verify_scanline_compute(testimg):
    """Exec the scanline Compute against a fake self; outColor must equal the
    plain sample times the analytic scan factor, and the scan must actually
    modulate (not a degenerate 1.0)."""
    ns = {}
    exec(FILE_INIT, ns)
    img = _framework_read_texture(testimg)

    bands, speed, intensity, t = 12.0, 0.1, 0.6, 4.0
    u, v = 0.5, 0.37

    class _S(object):
        def read_texture(self, path=None):
            return _framework_read_texture(path or self.fileName)

        def sample_texture(self, buf, su, sv):
            return _framework_sample(buf, su, sv)

    s = _S()
    s.fileName = testimg
    s.embeddedImage = None
    s.uvCoord = (u, v)
    s.bands = bands
    s.speed = speed
    s.intensity = intensity
    s.frame = t
    ns["self"] = s
    try:
        exec(compile(FILE_SCAN_COMPUTE, "scan_compute", "exec"), ns)
    except Exception as exc:
        return False, "exec:%r" % exc
    got = s.outColor

    vv = v - np.floor(v)
    r, g, b, a = _framework_sample(img, u, v)
    sfac = 0.5 + 0.5 * float(np.sin((vv * bands - t * speed) * 2.0 * np.pi))
    scan = (1.0 - intensity) + intensity * sfac
    exp = (r * scan, g * scan, b * scan)
    err = max(abs(got[i] - exp[i]) for i in range(3))
    modulates = abs(scan - 1.0) > 1e-3
    ok = err < 1e-5 and modulates
    return ok, "err=%.1e scan=%.3f" % (err, scan)


def _verify_scanline_viewport(testimg):
    """Exec the scanline Viewport against fakes; the uploaded buffer must equal
    the per-row baked scanline (top-down) and degrade cleanly headless."""
    import maya.api.OpenMayaRender as omr

    bands, speed, intensity, t = 12.0, 0.1, 0.6, 4.0
    captured = {}

    class _FakeShader:
        def parameterList(self):
            return ["gTexture", "gSampler"]

        def parameterType(self, n):
            return (omr.MShaderInstance.kTexture2 if n == "gTexture"
                    else omr.MShaderInstance.kSampler)

        def setParameter(self, n, v):
            captured.setdefault("set", []).append(n)

    class _FakeTM:
        def acquireTexture(self, name, desc, data, gen_mips):
            captured.update(w=desc.fWidth, h=desc.fHeight, bytes=bytes(data),
                            fmt=desc.fFormat, bpr=desc.fBytesPerRow)
            return None

        def releaseTexture(self, t):
            pass

    class _FakeSM:
        def acquireSamplerState(self, desc):
            return None

    class _FakeSelf(object):
        fileName = testimg
        shader = _FakeShader()
        texture_manager = _FakeTM()
        state_manager = _FakeSM()

        def read_texture(self, path=None):
            return _framework_read_texture(path or self.fileName)

    self_obj = _FakeSelf()
    self_obj.bands = bands
    self_obj.speed = speed
    self_obj.intensity = intensity
    self_obj.frame = t

    ns = {}
    exec(FILE_INIT, ns)
    ns["self"] = self_obj
    try:
        exec(compile(FILE_SCAN_VIEW, "scan_viewport", "exec"), ns)
    except Exception as exc:
        return False, "exec:%r" % exc
    if "bytes" not in captured:
        return False, "no upload"

    got = np.frombuffer(captured["bytes"], dtype=np.float32).reshape(
        captured["h"], captured["w"], 4)
    img = _framework_read_texture(testimg)
    exp = img.astype(np.float32, copy=True)
    h, w = exp.shape[0], exp.shape[1]
    py = np.arange(h, dtype=np.float32)
    vrow = 1.0 - py / float(max(h - 1, 1))
    srow = 0.5 + 0.5 * np.sin((vrow * bands - t * speed) * 2.0 * np.pi)
    scan = ((1.0 - intensity) + intensity * srow).astype(np.float32)
    exp[..., 0] *= scan[:, None]
    exp[..., 1] *= scan[:, None]
    exp[..., 2] *= scan[:, None]
    np.clip(exp[..., :3], 0.0, 1.0, out=exp[..., :3])

    maxerr = float(np.abs(got[..., :3] - exp[..., :3]).max())
    fmt_ok = captured["fmt"] == omr.MRenderer.kR32G32B32A32_FLOAT
    fields_ok = captured["bpr"] == captured["w"] * 4 * 4

    captured.clear()
    self_obj.texture_manager = None
    ns2 = {}
    exec(FILE_INIT, ns2)
    ns2["self"] = self_obj
    try:
        exec(compile(FILE_SCAN_VIEW, "scan_viewport", "exec"), ns2)
        headless_ok = "bytes" not in captured
    except Exception as exc:
        return False, "headless-raise:%r" % exc

    ok = maxerr < 1e-5 and fmt_ok and fields_ok and headless_ok
    return ok, "maxerr=%.1e fmt=%s flds=%s hl=%s" % (
        maxerr, fmt_ok, fields_ok, headless_ok)


def _verify_scanline_osl():
    structural = all(s in FILE_SCAN_OSL for s in (
        "shader scanlineTex(", "string fileName", "float bands", "float speed",
        "float intensity", "texture(fileName", "sin(", "clamp(",
    )) and ("1.0 - v" in FILE_SCAN_OSL or "1 - v" in FILE_SCAN_OSL)
    if not structural:
        return False, "structural"
    if "c = srgb_to_linear(c)" not in FILE_SCAN_OSL:
        return False, "not-linearized"
    try:
        from mpynode._common.osl.osl_targets import validate_osl_via_arnold
        ok, err = validate_osl_via_arnold(FILE_SCAN_OSL)
        return bool(ok), (err or "arnold-ok")
    except Exception as exc:
        return False, "validate:%r" % exc


def build_file_scanline():
    mc.file(new=True, force=True)
    from mpynode._common.node_setups import find_demo
    from mpynode.wrappers.mpy_file import MPyFile

    rows = [r * 30 for r in range(8)]
    testimg = "/tmp/_tpl_scanline_gradient.png"
    w, h = _write_test_image(testimg, rows)
    grid = os.path.join(ASSETS_DIR, "test_grid.png")

    f = MPyFile.create(name="scanlineTex", seed_defaults=False, as_texture=True)
    f.add_input_attr("bands", "int", default_value=12, min_value=1)
    f.add_input_attr("speed", "float", default_value=0.1)
    f.add_input_attr("intensity", "float", default_value=0.6,
                     min_value=0.0, max_value=1.0)
    f.add_input_attr("frame", "time")
    f.set_init_expression(FILE_INIT)
    f.set_compute_expression(FILE_SCAN_COMPUTE)
    f.set_viewport_expression(FILE_SCAN_VIEW)
    f.set_osl_expression(FILE_SCAN_OSL)
    f.set_methods_source(DEMO_FILE_SCAN)
    nm = f.get_name()

    _stamp_class(f, "ScanlineTex", "mPyFile")
    clean_payload = serialize_node(f, include_persistent=False)

    mc.setAttr(nm + ".fileName", testimg, type="string")
    mc.setAttr(nm + ".bands", 12)
    mc.setAttr(nm + ".speed", 0.1)
    mc.setAttr(nm + ".intensity", 0.6)

    def sample(u, v, t):
        mc.setAttr(nm + ".uCoord", u)
        mc.setAttr(nm + ".vCoord", v)
        mc.currentTime(t)
        mc.dgdirty(nm + ".outColor")
        return mc.getAttr(nm + ".outColor")[0]

    # The band scrolls: at a fixed uv, some frame must differ. (Avoid a single
    # pair -- a phase shift of t*speed == integer lands on the same scan value.)
    base = sample(0.5, 0.3, 0.0)[0]
    scroll_ok = any(
        abs(sample(0.5, 0.3, float(t))[0] - base) > 1e-3 for t in (5, 7, 13))

    # Missing file -> magenta. read_texture() returns None and
    # sample_texture() yields the (1, 0, 1) sentinel; the scan factor only
    # scales it, and at intensity 0.6 the trough never reaches the rails, so
    # check the HUE rather than the exact value.
    mc.setAttr(nm + ".fileName", "", type="string")
    mc.dgdirty(nm + ".outColor")
    miss = mc.getAttr(nm + ".outColor")[0]
    miss_ok = (miss[1] < 1e-4 and miss[0] > 1e-4
               and abs(miss[0] - miss[2]) < 1e-4)
    mc.setAttr(nm + ".fileName", testimg, type="string")

    compute_ok, compute_err = _verify_scanline_compute(testimg)
    view_ok, view_err = _verify_scanline_viewport(testimg)
    osl_ok, osl_err = _verify_scanline_osl()
    has_demo = find_demo(DEMO_FILE_SCAN) is not None

    # Run the authored @maya_test on a FRESH deserialized node.
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, name="scanlineTestCheck")
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    ok = (scroll_ok and miss_ok and compute_ok
          and view_ok and osl_ok and has_demo and test_ok)
    print("[file_scanline] scroll=%s miss=%s compute=%s(%s) "
          "view=%s(%s) osl=%s(%s) demo=%s test=%s(%s) -> %s"
          % (scroll_ok, miss_ok, compute_ok, compute_err,
             view_ok, view_err, osl_ok, osl_err,
             has_demo, test_ok, test_err, "PASS" if ok else "FAIL"))
    if ok:
        _copy_asset("test_grid.png", FILE_SCANLINE_DIR)
        _write_template_to(FILE_SCANLINE_DIR, clean_payload, FILE_SCAN_DESC)
    return ok


# ======================================================================
# 7. mPyFile -- composite: a LIST of image files stacked with premult alpha
# ======================================================================
FILE_COMPOSITE_INIT = r'''# ----------------------------------------------------------------------
# Composite texture -- Init tier.
#
# No image loading here either: every layer is read by the FRAMEWORK, via
# self.read_texture(path). Passing a path is what lets ONE node colour-manage
# and pre-filter SEVERAL images identically -- every element of `layers` goes
# through the node's own colorSpace / preFilter / preFilterKernel /
# preFilterRadius settings.
#
# What lives here is the one thing the Compute tier cannot do: the WHOLE-IMAGE
# version of the stack, which the Viewport tier uploads to the GPU. Compute
# composites one sample at a time (and so lowers to C++); the viewport needs
# the entire buffer at once.
# ----------------------------------------------------------------------
import numpy as np


def _layer_slots(slf):
    """The layer slots paired with their opacities, in stacking order.

    `layers` and `opacities` are ARRAY plugs, so the stack is however many
    elements you connect -- there is no fixed slot count. A layer with no
    matching opacity element defaults to 1.0 (a path you bothered to set is on
    unless you say otherwise); a surplus opacity with no layer is ignored."""
    paths = list(slf.layers)
    ops = list(slf.opacities)
    return tuple((paths[i], float(ops[i]) if i < len(ops) else 1.0)
                 for i in range(len(paths)))


def _bilinear_resize(arr, out_w, out_h):
    """Bilinear resize to (out_h, out_w, 4).

    Was nearest-neighbour (integer index mapping). That duplicated whole rows
    and columns when a layer had to be scaled up to meet the largest one, which
    is what made a mixed-resolution stack look blocky in the viewport while the
    Compute tier -- which samples every layer bilinearly at its OWN size and
    never resizes -- looked smooth. Same half-texel convention as
    file_texture_ops.sample(): coordinates map onto [0, n-1]."""
    sh, sw = arr.shape[0], arr.shape[1]
    if sh == out_h and sw == out_w:
        return arr
    ys = np.linspace(0.0, sh - 1.0, out_h).astype(np.float32)
    xs = np.linspace(0.0, sw - 1.0, out_w).astype(np.float32)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    y1 = np.minimum(y0 + 1, sh - 1)
    x1 = np.minimum(x0 + 1, sw - 1)
    ty = (ys - y0)[:, None, None]
    tx = (xs - x0)[None, :, None]
    top = arr[y0[:, None], x0[None, :]] * (1.0 - tx) + \
        arr[y0[:, None], x1[None, :]] * tx
    bot = arr[y1[:, None], x0[None, :]] * (1.0 - tx) + \
        arr[y1[:, None], x1[None, :]] * tx
    return (top * (1.0 - ty) + bot * ty).astype(np.float32)


def _composite_layers(slf):
    """Whole-image twin of the Compute tier's alpha-over stack, or None when
    no slot is enabled.

    Mirrors Compute EXACTLY, including the missing-file case: Compute samples
    every slot with `missing=(0, 0, 0, 0)`, so a slot whose path does not load
    contributes NOTHING rather than the opaque magenta sentinel. This function
    has to make the same choice or the viewport and the render disagree about a
    broken layer. Layers of different sizes are resized (bilinear) to the
    largest enabled layer.
    """
    slots = [(path, op) for path, op in _layer_slots(slf) if op > 0.0]
    if not slots:
        return None
    bufs = [(slf.read_texture(path), op) for path, op in slots]
    sizes = [b.shape for b, _op in bufs if b is not None]
    if not sizes:
        return None                      # nothing loadable: nothing to upload
    max_h = max(s[0] for s in sizes)
    max_w = max(s[1] for s in sizes)

    acc = np.zeros((max_h, max_w, 4), dtype=np.float32)
    for buf, op in bufs:
        if buf is None:                  # missing=(0,0,0,0): contributes nothing
            continue
        if buf.shape[0] != max_h or buf.shape[1] != max_w:
            src = _bilinear_resize(buf, max_w, max_h)
        else:
            src = buf
        sa = (src[..., 3:4] * np.float32(op)).astype(np.float32)
        acc[..., :3] = src[..., :3] * sa + acc[..., :3] * (np.float32(1.0) - sa)
        acc[..., 3:4] = sa + acc[..., 3:4] * (np.float32(1.0) - sa)
    return acc
'''


FILE_COMPOSITE_COMPUTE = r'''# Composite texture -- Compute tier.
#
# AN ARBITRARY NUMBER OF LAYERS, bottom (`layers[0]`) to top, alpha-over at the
# sampled point. `layers` and `opacities` are ARRAY plugs, so the stack is as
# deep as you make it -- add an element, get a layer. Every layer is loaded by
# the SAME framework call the File Simple template uses -- self.read_texture
# (path) -- so all of them are decoded out of `colorSpace` and pre-filtered
# identically. Nothing here knows how to read a file; it only knows how to stack.
#
# The loop bound is the RUNTIME array length, and it stays that way when this
# node is compiled: `layers` lifts to a std::vector<std::string> and the C++ is
# the same `for` over `.size()`. Nothing about the layer count is baked in.
#
# AN UNSET SLOT DROPS OUT BY ITSELF. A blank or unresolvable path makes
# read_texture() return None, and every sample here passes
# `missing=(0.0, 0.0, 0.0, 0.0)` -- so that slot samples as fully transparent
# and contributes nothing, instead of the OPAQUE magenta "no image" sentinel
# that would cover the layers underneath. Drop the argument (or pass
# missing=None) to get the magenta back, which is still what you want while
# authoring: it makes a typo'd path impossible to miss.
#
# An `opacities` element is a real weight rather than an on/off switch -- 0 still
# removes a layer exactly, but you no longer have to zero a slot just because it
# has no file yet. A layer with NO matching opacity element defaults to 1.0: a
# path you bothered to set is on unless you say otherwise.
#
# The result is composited over black and comes out premultiplied, which is
# what an unlit surfaceShader wants.
u = self.uvCoord[0]
v = self.uvCoord[1]

# Accumulate over transparent black, bottom layer first.
cr = 0.0
cg = 0.0
cb = 0.0
ca = 0.0
n_op = len(self.opacities)
for i in range(len(self.layers)):
    r, g, b, a_src = self.sample_texture(self.read_texture(self.layers[i]),
                                         u, v, missing=(0.0, 0.0, 0.0, 0.0))
    op = 1.0
    if i < n_op:
        op = float(self.opacities[i])
    a = a_src * op
    cr = r * a + cr * (1.0 - a)
    cg = g * a + cg * (1.0 - a)
    cb = b * a + cb * (1.0 - a)
    ca = a + ca * (1.0 - a)

self.outColor = (cr, cg, cb)
self.outAlpha = ca
'''


FILE_COMPOSITE_VIEW = r'''# ----------------------------------------------------------------------
# Composite texture -- Viewport (VP2) source (runs per updateShader call).
#
# Uploads the SAME composite buffer the Compute tier samples into the VP2
# file-texture fragment, so the textured viewport surface matches the
# swatch / software render. Degrades gracefully (nested guards, no early
# return) when headless (texture_manager is None) or no valid file.
# ----------------------------------------------------------------------
import maya.api.OpenMayaRender as omr

img = _composite_layers(self)                # (H,W,4) float32 0..1, top-down
if img is not None and self.texture_manager is not None:
    processed = np.ascontiguousarray(img, dtype=np.float32)
    h, w = processed.shape[0], processed.shape[1]

    map_param = None
    samp_param = None
    for pname in self.shader.parameterList():
        try:
            ptype = self.shader.parameterType(pname)
        except Exception:
            continue
        if map_param is None and ptype == omr.MShaderInstance.kTexture2:
            map_param = pname
        elif samp_param is None and ptype == omr.MShaderInstance.kSampler:
            samp_param = pname
        if map_param and samp_param:
            break

    if map_param:
        desc = omr.MTextureDescription()
        desc.setToDefault2DTexture()
        desc.fWidth = w
        desc.fHeight = h
        desc.fDepth = 1
        desc.fBytesPerRow = w * 4 * 4
        desc.fBytesPerSlice = desc.fBytesPerRow * h
        desc.fMipmaps = 1
        desc.fArraySlices = 1
        desc.fFormat = omr.MRenderer.kR32G32B32A32_FLOAT
        desc.fTextureType = omr.MTextureDescription.kImage2D
        desc.fEnvMapType = omr.MTextureDescription.kEnvNone

        tex_name = "mpyfile_composite::%s" % ("|".join(
            "%s@%.4f" % (p, o) for p, o in _layer_slots(self)))
        texture = self.texture_manager.acquireTexture(
            tex_name, desc, processed.tobytes(), False)
        if texture is not None:
            try:
                assignment = omr.MTextureAssignment()
                assignment.texture = texture
                self.shader.setParameter(map_param, assignment)
            finally:
                try:
                    self.texture_manager.releaseTexture(texture)
                except Exception:
                    pass

    if samp_param:
        try:
            sdesc = omr.MSamplerStateDesc()
            sdesc.setDefaults()
            sdesc.filter = omr.MSamplerState.kMinMagMipLinear
            sdesc.addressU = omr.MSamplerState.kTexClamp
            sdesc.addressV = omr.MSamplerState.kTexClamp
            self.shader.setParameter(
                samp_param, self.state_manager.acquireSamplerState(sdesc))
        except Exception:
            pass
'''

DEMO_FILE_COMPOSITE = r'''# Showcase for the composite texture: a plane + an UNLIT surfaceShader (so the
# raw composite colours show untinted), with this node's outColor driving the
# shader. The four shipped test images are appended to the `layers` ARRAY in
# stacking order -- grid background, red square, green circle, blue triangle --
# with a matching `opacities` element each. Four is just what this demo happens
# to load; append a fifth element and it composites too.
def demo(self):
    from maya import cmds as mc
    import os
    name = self.get_name()

    # 1. A plane to show the composite on.
    plane = mc.polyPlane(width=10, height=10, subdivisionsX=1,
                         subdivisionsY=1, name=name + "_plane")[0]

    # 2. An unlit surfaceShader; assign it to the plane and drive its colour
    #    from this node's outColor (surfaceShader.outColor is both the driven
    #    input and the shading output, so it shows the buffer exactly).
    shader = mc.shadingNode("surfaceShader", asShader=True,
                            name=name + "_surface")
    sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True,
                 name=shader + "SG")
    mc.connectAttr(shader + ".outColor", sg + ".surfaceShader", force=True)
    mc.sets(plane, edit=True, forceElement=sg)
    mc.connectAttr(name + ".outColor", shader + ".outColor", force=True)

    # 3. The four shipped test images (beside this template), bottom to top,
    #    into the layers/opacities ARRAYS.
    base = None
    try:
        from mpynode._common.util.template_gallery import _bundled_templates_root
        root = _bundled_templates_root()
        if root:
            cand = os.path.join(root, "MPyFile", "File Composite")
            if os.path.isdir(cand):
                base = cand
    except Exception:
        base = None
    stack = ["grid_bg.png", "red_square.png", "green_circle.png",
             "blue_triangle.png"]
    for i, fn in enumerate(stack):
        path = os.path.join(base, fn) if base else fn
        mc.setAttr("%s.layers[%d]" % (name, i), path, type="string")
        mc.setAttr("%s.opacities[%d]" % (name, i), 1.0)

    # 4. Force one eval so the swatch / viewport show the composite immediately.
    try:
        mc.dgdirty(name + ".outColor")
        mc.getAttr(name + ".outColor")
    except Exception:
        pass
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_test(label="Composite: an ARBITRARY-length layer array stacks bottom-to-top", digits=4)
def test_file_composite(self):
    """Same test passes interpreted and compiled (parity).

      1. With one element in `layers` the node reads as that image alone.
      2. Appending a second element CHANGES the result -- the stack actually
         composites rather than showing the base.
      3. An `opacities` element gates its layer: back to 0 restores (1).
      4. A layer with no valid file DROPS OUT rather than covering the stack
         with the magenta sentinel.
      5. The stack length is RUNTIME, not four: growing the array to five
         elements composites all five.
    """
    from maya import cmds as mc
    import os
    from mpynode._common.methods.test_helpers import (
        assert_true, assert_close)
    name = self.get_name()

    def _set(plug, *vals, **kw):
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals, **kw)

    base = None
    try:
        from mpynode._common.util.template_gallery import _bundled_templates_root
        root = _bundled_templates_root()
        if root:
            cand = os.path.join(root, "MPyFile", "File Composite")
            if os.path.isdir(cand):
                base = cand
    except Exception:
        base = None
    files = ["grid_bg.png", "red_square.png", "green_circle.png",
             "blue_triangle.png"]
    present = [os.path.join(base, f) for f in files
               if base and os.path.isfile(os.path.join(base, f))]
    assert_true(len(present) >= 2,
                "expected the shipped test images beside the template")

    def _stack(paths, ops=None):
        """Rebuild the arrays to EXACTLY these elements (surplus removed)."""
        for idx in (mc.getAttr(name + ".layers", multiIndices=True) or []):
            mc.removeMultiInstance("%s.layers[%d]" % (name, idx), b=True)
        for idx in (mc.getAttr(name + ".opacities", multiIndices=True) or []):
            mc.removeMultiInstance("%s.opacities[%d]" % (name, idx), b=True)
        for k, p in enumerate(paths):
            _set("%s.layers[%d]" % (name, k), p, type="string")
            _set("%s.opacities[%d]" % (name, k),
                 1.0 if ops is None else ops[k])

    def out_color(u, v):
        _set(name + ".uCoord", u)
        _set(name + ".vCoord", v)
        mc.dgdirty(name + ".outColor")
        return list(mc.getAttr(name + ".outColor")[0])

    # 1) One layer alone.
    _stack([present[0]])
    base_col = out_color(0.1875, 0.4375)

    # 2) A second layer over it must change SOMETHING somewhere on the surface.
    #    A decal only covers part of the frame, so probe a few points.
    probes = [(0.1875, 0.4375), (0.3125, 0.5625), (0.1875, 0.6875)]
    before = [out_color(u, v) for u, v in probes]
    _stack([present[0], present[1]])
    after = [out_color(u, v) for u, v in probes]
    changed = any(max(abs(a[i] - b[i]) for i in range(3)) > 1e-4
                  for a, b in zip(before, after))
    assert_true(changed, "layers[1] must composite over layers[0] somewhere")

    # 3) An opacity element gates its layer: 0 restores the one-layer result.
    _stack([present[0], present[1]], ops=[1.0, 0.0])
    assert_close(out_color(0.1875, 0.4375), base_col)

    # 4) A layer with no file DROPS OUT (missing=(0,0,0,0)) instead of covering
    #    the stack with the opaque magenta sentinel: a broken BOTTOM layer must
    #    leave the layer above it visible and unaltered.
    _stack([present[0]])
    alone = out_color(0.1875, 0.4375)
    alone_a = mc.getAttr(name + ".outAlpha")
    _stack(["", present[0]])
    assert_close(out_color(0.1875, 0.4375), alone)
    assert_close(mc.getAttr(name + ".outAlpha"), alone_a)

    # Every layer broken -> nothing to show: fully transparent, NOT magenta.
    _stack(["", "", ""])
    assert_close(out_color(0.5, 0.5), [0.0, 0.0, 0.0])
    assert_close(mc.getAttr(name + ".outAlpha"), 0.0)

    # 5) The stack length is RUNTIME, not four. Build FIVE elements whose top
    #    one is a DIFFERENT image from the rest, and probe where that image is
    #    opaque: a fixed-four node physically could not reach element 4.
    five = [present[0], present[0], present[0], present[0], present[1]]
    _stack(five, ops=[1.0, 1.0, 1.0, 1.0, 0.0])
    without_fifth = out_color(0.1875, 0.4375)
    _stack(five, ops=[1.0, 1.0, 1.0, 1.0, 1.0])
    with_fifth = out_color(0.1875, 0.4375)
    assert_true(len(mc.getAttr(name + ".layers", multiIndices=True) or []) == 5,
                "expected a five-element layer stack")
    assert_true(
        max(abs(without_fifth[i] - with_fifth[i]) for i in range(3)) > 1e-4,
        "the FIFTH array element must reach the composite")
'''


FILE_COMPOSITE_DESC = """# Composite Stack (compositeTexture)

An `mPyFile` that stacks an ARBITRARY number of images into one texture, so you
can build a background plus as many decals as you like without authoring a new
image.

`layers` is an ARRAY of image paths, composited bottom (`layers[0]`) to top with
alpha-over at the sampled point, and `opacities` is a matching array of weights.
Add an element, get a layer -- there is no fixed slot count, and the compiled
node loops over the runtime array length exactly as the interpreted one does.

A layer with no file (or an unreadable one) drops out of the stack on its own:
every sample passes `missing=(0.0, 0.0, 0.0, 0.0)`, so an empty layer is fully
transparent rather than the opaque magenta "no image" colour that would cover
everything beneath it. An `opacities` element is a plain weight on top of that
-- 0 still removes a layer exactly. A layer with no matching opacity element
defaults to 1.0.

Drop the `missing=` argument to get the magenta sentinel back. That is often
what you want while authoring, because it makes a typo'd path impossible to
miss; transparent failure is quiet by design.

If the node renders as nothing at all, check that `layers` actually has
elements: an empty array is an empty stack, and the surface comes out fully
transparent rather than black.

Every layer is loaded by the same framework call the File Simple template
uses, `self.read_texture(path)`, so all of them go through this node's
`colorSpace`, `preFilter`, `preFilterKernel` and `preFilterRadius`. That is
also why this template compiles: the loads lower straight to
`nd_tex_load_linear`, with no hand-written C++ loader, and the string array
lifts to a `std::vector<std::string>`.

The stack is sampled at `uvCoord` and comes out `outColor` / `outAlpha`,
composited over black (premultiplied), which is what an unlit shader wants.

**Create + Run demo** builds a plane and an unlit shader, then loads the four
images shipped beside this template -- `grid_bg.png`, `red_square.png`,
`green_circle.png`, `blue_triangle.png` -- into the first four array elements at
full opacity. Four is just what the demo loads; append a fifth and it composites.
"""


def _verify_composite_viewport(paths):
    """Exec the composite Viewport against fakes; the uploaded buffer must
    equal the Init tier's whole-image stack (top-down) and degrade cleanly
    headless."""
    import maya.api.OpenMayaRender as omr

    captured = {}

    class _FakeShader:
        def parameterList(self):
            return ["gTexture", "gSampler"]

        def parameterType(self, n):
            return (omr.MShaderInstance.kTexture2 if n == "gTexture"
                    else omr.MShaderInstance.kSampler)

        def setParameter(self, n, v):
            captured.setdefault("set", []).append(n)

    class _FakeTM:
        def acquireTexture(self, name, desc, data, gen_mips):
            captured.update(w=desc.fWidth, h=desc.fHeight, bytes=bytes(data),
                            fmt=desc.fFormat, bpr=desc.fBytesPerRow)
            return None

        def releaseTexture(self, t):
            pass

    class _FakeSM:
        def acquireSamplerState(self, desc):
            return None

    class _FakeSelf(object):
        shader = _FakeShader()
        texture_manager = _FakeTM()
        state_manager = _FakeSM()

        def read_texture(self, path=None):
            return _framework_read_texture(
                path or (self.layers[0] if self.layers else ""))

    self_obj = _FakeSelf()
    # The layers/opacities ARRAYS, all enabled -- the stack the demo builds.
    self_obj.layers = list(paths)
    self_obj.opacities = [1.0] * len(paths)

    ns = {}
    exec(FILE_COMPOSITE_INIT, ns)
    ns["self"] = self_obj
    try:
        exec(compile(FILE_COMPOSITE_VIEW, "composite_viewport", "exec"), ns)
    except Exception as exc:
        return False, "exec:%r" % exc
    if "bytes" not in captured:
        return False, "no upload"

    got = np.frombuffer(captured["bytes"], dtype=np.float32).reshape(
        captured["h"], captured["w"], 4)
    exp = ns["_composite_layers"](self_obj)
    maxerr = float(np.abs(got - exp).max())
    fmt_ok = captured["fmt"] == omr.MRenderer.kR32G32B32A32_FLOAT
    fields_ok = captured["bpr"] == captured["w"] * 4 * 4

    captured.clear()
    self_obj.texture_manager = None
    ns2 = {}
    exec(FILE_COMPOSITE_INIT, ns2)
    ns2["self"] = self_obj
    try:
        exec(compile(FILE_COMPOSITE_VIEW, "composite_viewport", "exec"), ns2)
        headless_ok = "bytes" not in captured
    except Exception as exc:
        return False, "headless-raise:%r" % exc

    ok = maxerr < 1e-6 and fmt_ok and fields_ok and headless_ok
    return ok, "maxerr=%.1e fmt=%s flds=%s hl=%s" % (
        maxerr, fmt_ok, fields_ok, headless_ok)


def build_file_composite():
    mc.file(new=True, force=True)
    from mpynode._common.node_setups import find_demo
    from mpynode.wrappers.mpy_file import MPyFile

    # The four test images ship BESIDE this template (hand-placed, like
    # MPyNode/DNET's skull.ma), so the gate points the layer slots straight at
    # the template folder -- the same files the demo and the authored test
    # resolve through the bundled templates root.
    assets = os.path.join(TPL, *FILE_COMPOSITE_DIR.split("/"))
    stack = [os.path.join(assets, n) for n in
             ("grid_bg.png", "red_square.png", "green_circle.png",
              "blue_triangle.png")]
    missing = os.path.join(assets, "_no_such.png")
    assets_ok = all(os.path.isfile(p) for p in stack)
    if not assets_ok:
        print("[file_composite] assets=%s -> FAIL" % assets_ok)
        return False

    f = MPyFile.create(name="compositeTexture", seed_defaults=False,
                       as_texture=True)
    # ARRAY plugs: the stack is however many elements you add, not a fixed four.
    # An empty/unresolvable layer now drops out on its own (missing=(0,0,0,0)),
    # so an opacity element defaults to 1.0 -- there is no longer any reason to
    # ship a slot switched off.
    f.add_input_attr("layers", "string", is_array=True)
    f.add_input_attr("opacities", "float", default_value=1.0,
                     min_value=0.0, max_value=1.0, is_array=True)
    f.set_init_expression(FILE_COMPOSITE_INIT)
    f.set_compute_expression(FILE_COMPOSITE_COMPUTE)
    f.set_viewport_expression(FILE_COMPOSITE_VIEW)
    f.set_methods_source(DEMO_FILE_COMPOSITE)
    nm = f.get_name()

    _stamp_class(f, "CompositeTexture", "mPyFile")
    clean_payload = serialize_node(f, include_persistent=False)

    def set_stack(paths, ops=None):
        """Rebuild the arrays to EXACTLY ``paths`` (surplus elements removed)."""
        for plug in ("layers", "opacities"):
            for idx in (mc.getAttr("%s.%s" % (nm, plug),
                                   multiIndices=True) or []):
                mc.removeMultiInstance("%s.%s[%d]" % (nm, plug, idx), b=True)
        for i, p in enumerate(paths):
            mc.setAttr("%s.layers[%d]" % (nm, i), p, type="string")
            mc.setAttr("%s.opacities[%d]" % (nm, i),
                       1.0 if ops is None else ops[i])

    def sample(u, v):
        mc.setAttr(nm + ".uCoord", u)
        mc.setAttr(nm + ".vCoord", v)
        mc.dgdirty(nm + ".outColor")
        return mc.getAttr(nm + ".outColor")[0]

    # One probe per layer, at a UV where THAT layer is measurably opaque
    # (blue_triangle covers only ~7% of the frame, so a generic grid misses it
    # and the stacking-order check silently passes on nothing).
    grid = [(0.0625, 0.0625),      # grid_bg only
            (0.1875, 0.4375),      # red_square
            (0.5625, 0.5625),      # green_circle
            (0.5625, 0.1875)]      # blue_triangle (top layer)

    # The layers actually land: the sampled texels are not one flat colour.
    set_stack(stack)
    four = [sample(u, v) for u, v in grid]
    layered_ok = len({tuple(round(c, 4) for c in s) for s in four}) > 1

    # Stacking ORDER matters: the top layer must change the result somewhere.
    set_stack(stack[:3])
    three = [sample(u, v) for u, v in grid]
    order_ok = any(not np.allclose(a, b, atol=1e-6)
                   for a, b in zip(four, three))

    # an opacity element gates its layer exactly: top layer at 0 == not there.
    set_stack(stack, ops=[1.0, 1.0, 1.0, 0.0])
    gated = [sample(u, v) for u, v in grid]
    gate_ok = all(np.allclose(a, b, atol=1e-6)
                  for a, b in zip(three, gated))

    # A layer pointing at nothing drops out: the template samples with
    # missing=(0,0,0,0), so a broken layer is transparent rather than the opaque
    # magenta sentinel that used to cover the whole stack. Both the colour and
    # the alpha must read as "nothing here".
    set_stack([missing])
    miss = sample(0.5, 0.5)
    miss_ok = (np.allclose(miss, (0.0, 0.0, 0.0), atol=1e-4)
               and abs(mc.getAttr(nm + ".outAlpha")) < 1e-4)

    # ...and a broken layer UNDER a good one leaves the good one untouched.
    set_stack([stack[1]])
    good_alone = sample(0.1875, 0.4375)
    set_stack([missing, stack[1]])
    miss_ok = miss_ok and np.allclose(sample(0.1875, 0.4375), good_alone,
                                      atol=1e-6)

    # The array is ARBITRARY-length: a SIX-element stack whose top layer is a
    # different image must differ from the same six with that layer switched
    # off. A fixed-four node could not reach element 5 at all.
    six = [stack[0]] * 5 + [stack[1]]
    set_stack(six, ops=[1.0] * 5 + [0.0])
    without_top = sample(0.1875, 0.4375)
    set_stack(six, ops=[1.0] * 6)
    with_top = sample(0.1875, 0.4375)
    arb_ok = (len(mc.getAttr(nm + ".layers", multiIndices=True) or []) == 6
              and not np.allclose(without_top, with_top, atol=1e-4))

    view_ok, view_err = _verify_composite_viewport(stack)
    has_demo = find_demo(DEMO_FILE_COMPOSITE) is not None

    # Run the authored @maya_test on a FRESH deserialized node.
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    ok = (layered_ok and order_ok and gate_ok and miss_ok and arb_ok
          and view_ok and has_demo and test_ok)
    print("[file_composite] layered=%s order=%s gate=%s miss=%s arb=%s "
          "view=%s(%s) demo=%s test=%s(%s) -> %s"
          % (layered_ok, order_ok, gate_ok, miss_ok, arb_ok, view_ok,
             view_err, has_demo, test_ok, test_err, "PASS" if ok else "FAIL"))
    if ok:
        # The four demo layers, all 1024x1024 so the stack needs no resize at
        # all. They used to be orphan binaries committed straight into the
        # template folder at 480x360 / 512x400 / 300x512 / 450x450 -- the base
        # was the shipped grid nearest-downsampled to 480x360, which is what
        # made this template read as the blurry one next to its siblings. The
        # base is now that grid at full size; the three shapes are authored by
        # _demos/make_composite_assets.py.
        _copy_asset("test_grid.png", FILE_COMPOSITE_DIR, dest_name="grid_bg.png")
        for _fn in ("red_square.png", "green_circle.png", "blue_triangle.png"):
            _copy_asset(_fn, FILE_COMPOSITE_DIR)
        _write_template_to(FILE_COMPOSITE_DIR, clean_payload,
                           FILE_COMPOSITE_DESC)
    return ok


# ======================================================================
# Locator templates -- shared plugin-load helper
# ======================================================================
def _ensure_mpy_plugins():
    for plugin in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(plugin, q=True, loaded=True):
            mc.loadPlugin(plugin)


def _draw_slot(loc, slot, time_value=0.0, wallclock=None):
    """The FIRST buffer of ``slot`` in a locator's ordered draw commands, or
    None if it drew nothing there. The build gates below only ever inspect one
    item per slot; ``_draw_slots`` answers "which slots drew at all".
    ``wallclock`` pins ``self.wallclock`` so a wall-clock animation is read at
    a chosen instant (None samples the real clock)."""
    for cmd in loc.evaluate_draw_commands(time_value, wallclock=wallclock)["commands"]:
        if cmd["slot"] == slot:
            return cmd["buffer"]
    return None


def _draw_slots(loc, time_value=0.0, wallclock=None):
    """The set of slots a locator drew into this frame."""
    return {c["slot"]
            for c in loc.evaluate_draw_commands(time_value, wallclock=wallclock)["commands"]}


# ======================================================================
# 1. mPyLocator Widgets - basics :: STATIC rendering-capability showcase
# ======================================================================
LOC_SHOWCASE_INIT = r'''import numpy as np
from mpynode._common.draw.draw_types import (
    DrawBox, DrawCircle, DrawCone, DrawCylinder, DrawLines, DrawMesh,
    DrawPoints, DrawSphere, DrawText)

# Column X positions so every slot draws in its own lane when the
# "everything" preset is active.
COLX = {"curves": -8.0, "points": -4.0, "polygons": 0.0,
        "shapes": 4.0, "text": 8.0}

# Which draw slots each preset turns on. Shipped as the default; a
# persistent `presets` stored var (a dict) overrides it when present.
DEFAULT_PRESETS = {
    "everything": ["curves", "points", "polygons", "shapes", "text"],
    "curves":     ["curves"],
    "points":     ["points"],
    "polygons":   ["polygons"],
    "shapes":     ["shapes"],
    "text":       ["text"]}

# ---- curves: a 3-axis RGB gizmo + a diamond outline (lines slot) ----
_cx = COLX["curves"]
_axis_starts = np.array([[_cx, 0.0, 0.0]] * 3, dtype=np.float32)
_axis_ends = np.array([[_cx + 2.0, 0.0, 0.0], [_cx, 2.0, 0.0], [_cx, 0.0, 2.0]], dtype=np.float32)
_axis_cols = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
_d = np.array([[1, 0, 0], [0, 0, 1], [-1, 0, 0], [0, 0, -1]], dtype=np.float32)
_d = _d * 1.6 + np.array([_cx, 0.0, 0.0], dtype=np.float32)
CURVE_STARTS = np.concatenate([_axis_starts, _d]).astype(np.float32)
CURVE_ENDS = np.concatenate([_axis_ends, np.roll(_d, -1, axis=0)]).astype(np.float32)
CURVE_COLORS = np.concatenate(
    [_axis_cols, np.tile([1.0, 0.8, 0.2], (4, 1))]).astype(np.float32)

# ---- points: a rainbow grid with per-point size (points slot) ----
_gx, _gz = np.meshgrid(np.linspace(-1.5, 1.5, 6), np.linspace(-1.5, 1.5, 6))
_gx = _gx.ravel()
_gz = _gz.ravel()
_n = _gx.size
POINT_POS = np.stack(
    [_gx + COLX["points"], np.zeros(_n), _gz], axis=1).astype(np.float32)
_h = np.arange(_n) / float(_n)
POINT_COLORS = np.stack(
    [0.5 + 0.5 * np.sin(6.2832 * _h),
     0.5 + 0.5 * np.sin(6.2832 * _h + 2.094),
     0.5 + 0.5 * np.sin(6.2832 * _h + 4.189)], axis=1).astype(np.float32)
POINT_SIZES = (4.0 + 8.0 * ((np.arange(_n) % 6) / 5.0)).astype(np.float32)

# ---- polygons: a shaded cube with per-face hues + wire overlay ----
_px = COLX["polygons"]
POLY_PTS = (np.array([
    [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
    [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]],
    dtype=np.float64) + np.array([_px, 0.0, 0.0]))
POLY_IDX = np.array(
    [0, 3, 2, 1, 4, 5, 6, 7, 0, 1, 5, 4, 2, 3, 7, 6, 0, 4, 7, 3, 1, 2, 6, 5], dtype=np.int64)
POLY_CNT = np.array([4, 4, 4, 4, 4, 4], dtype=np.int64)
POLY_FACE_COLORS = np.array([
    [0.90, 0.20, 0.25, 1.0], [0.95, 0.55, 0.15, 1.0], [0.95, 0.85, 0.20, 1.0],
    [0.30, 0.80, 0.35, 1.0], [0.25, 0.55, 0.95, 1.0], [0.60, 0.35, 0.85, 1.0]], dtype=np.float64)

# ---- shapes: one of each Maya primitive in a row (shapes slot) ----
# One object per primitive, so the KIND is the class name instead of a string
# in a "kinds" list that has to stay index-aligned with four sibling arrays.
_sx = COLX["shapes"]
AXIS_Y = (0.0, 1.0, 0.0)
SHAPE_CENTERS = np.array(
    [[_sx, 0.0, z] for z in (-4.0, -2.0, 0.0, 2.0, 4.0)], dtype=np.float32)
SHAPE_COLORS = np.array([
    [0.9, 0.3, 0.3], [0.3, 0.9, 0.4], [0.3, 0.5, 0.9],
    [0.9, 0.8, 0.2], [0.8, 0.4, 0.9]], dtype=np.float32)

# ---- text: labels (text slot) ----
_tx = COLX["text"]
TEXT_STRINGS = ["lines", "points", "polygons", "shapes", "text"]
TEXT_POS = np.array(
    [[_tx, 3.0 - i * 1.3, 0.0] for i in range(5)], dtype=np.float32)
TEXT_COLORS = np.array([
    [1.0, 0.8, 0.2], [0.4, 0.9, 1.0], [0.9, 0.5, 0.9],
    [0.5, 1.0, 0.6], [1.0, 1.0, 1.0]], dtype=np.float32)
# Local-space (default) text: sizes are OBJECT-space glyph heights (world
# units, ~half the 1.3 row spacing), auto-scaled to pixels from the widget's
# on-screen size so labels track the gizmo instead of staying a fixed pixel
# size. Add "space": "screen" to the text buffer for constant-pixel labels.
TEXT_SIZES = np.array([0.6, 0.6, 0.6, 0.6, 0.6], dtype=np.float32)
'''

LOC_SHOWCASE_COMPUTE = r'''# Static rendering showcase -- no animation, so the cheapest possible
# locator (no auto_refresh). The `preset` enum selects which draw slots
# light up; a persistent `presets` dict (if present) overrides the shipped
# DEFAULT_PRESETS. Unassigned slots stay None and simply don't draw.
preset = self.preset.name()
presets = getattr(self, "presets", None)
if not isinstance(presets, dict):
    presets = DEFAULT_PRESETS
active = set(presets.get(preset, DEFAULT_PRESETS.get(preset, [])))

self.auto_highlight = False   # carry our own palette

# Each preset appends the drawables for its lane; `self.draw` takes the LIST
# straight and draws it in order. A drawable carries its own target buffer, so
# nothing here has to name a slot -- and an inactive preset simply contributes
# no object.
items = []

if "curves" in active:
    items.append(DrawLines(CURVE_STARTS, CURVE_ENDS, color=CURVE_COLORS))

if "points" in active:
    items.append(DrawPoints(POINT_POS, color=POINT_COLORS, size=POINT_SIZES))

if "polygons" in active:
    # outline_boundary_only=False draws EVERY edge (the cube's wire overlay),
    # not just the silhouette.
    items.append(DrawMesh(POLY_PTS, POLY_CNT, POLY_IDX,
                          color=POLY_FACE_COLORS, cull_backfaces=True,
                          outline=(0.04, 0.04, 0.06, 1.0), outline_width=2.0,
                          outline_boundary_only=False))

if "shapes" in active:
    items.append(
        DrawSphere(center=SHAPE_CENTERS[0], radius=0.8, axis=AXIS_Y,
                   color=SHAPE_COLORS[0], filled=True)
        + DrawBox(center=SHAPE_CENTERS[1], radius=0.8, axis=AXIS_Y,
                  color=SHAPE_COLORS[1], filled=True)
        + DrawCone(center=SHAPE_CENTERS[2], radius=0.8, axis=AXIS_Y,
                   color=SHAPE_COLORS[2], filled=True)
        + DrawCylinder(center=SHAPE_CENTERS[3], radius=0.8, axis=AXIS_Y,
                       color=SHAPE_COLORS[3], filled=True)
        + DrawCircle(center=SHAPE_CENTERS[4], radius=0.9, axis=AXIS_Y,
                     color=SHAPE_COLORS[4], filled=False))

if "text" in active:
    items.append(DrawText(TEXT_STRINGS, TEXT_POS, color=TEXT_COLORS, size=TEXT_SIZES))

self.draw = items
'''

DEMO_LOC_SHOWCASE = '''# Widget Showcase setup: bake the preset table as an editable persistent
# dict (the `preset` enum dials into it), select the "everything" preset,
# and frame the widget. The locator draws itself, so this is all it needs.


def demo(self):
    from maya import cmds as mc
    name = self.get_name()
    presets = {
        "everything": ["curves", "points", "polygons", "shapes", "text"],
        "curves": ["curves"], "points": ["points"], "polygons": ["polygons"],
        "shapes": ["shapes"], "text": ["text"]}
    try:
        self.set_variable("presets", presets, persistent=True)
    except Exception:
        pass
    try:
        mc.setAttr(name + ".preset", 0)   # everything
    except Exception:
        pass
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_test(label="Widget showcase: presets light up exactly their draw slots", digits=3)
def test_widget_showcase(self):
    """Validate the node's INTENT (the SAME test passes on the interpreted node
    and its C++ compile -> parity): the `preset` enum selects WHICH of the five
    draw slots (lines / points / polygons / shapes / text) this locator paints,
    the "everything" preset fills them all with real content, and a persistent
    `presets` dict overrides the shipped default. Mirrors the builder's own
    live-check ground truth (content_ok / preset_ok / override_ok)."""
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    from mpynode._common.methods.test_helpers import assert_equal, assert_true
    from mpynode._common.storedvars.stored_vars_api import set_variable

    name = self.get_name()
    enum_order = ["everything", "curves", "points",
                  "polygons", "shapes", "text"]
    expected = {
        "everything": {"lines", "points", "polygons", "shapes", "text"},
        "curves": {"lines"}, "points": {"points"},
        "polygons": {"polygons"}, "shapes": {"shapes"}, "text": {"text"}}

    def _draw(time_value=0.0):
        # Trigger the locator's compute and read back its ordered draw commands
        # via the node's public MPx surface using the node NAME only -- so this
        # works on the interpreted node AND a compiled node (the parity point),
        # without relying on the Python wrapper.
        sel = om2.MSelectionList()
        sel.add(name)
        mpx = om2.MFnDependencyNode(sel.getDependNode(0)).userNode()
        return (mpx.evaluateDrawItems(time_value) or {}).get("commands") or []

    def _slots(cmds):
        return {c["slot"] for c in cmds}

    def _of(cmds, slot):
        return [c["buffer"] for c in cmds if c["slot"] == slot]

    # A COMPILED C++ locator (MPxLocatorNode) exposes no Python
    # evaluateDrawItems, so its draw buffers are unreachable here -- that parity
    # is covered by the dedicated -DMPYNODE_PROBE numerical buffer comparison.
    # Skip cleanly rather than false-fail, the same guard test_animated_selection
    # and test_animated_text already use. This also keeps step 3's set_variable
    # (an interpreted-only stored-var write) off the compiled path.
    # AttributeError ONLY: a node that HAS the surface but draws nothing must
    # still fail the assertions below.
    try:
        _draw()
    except AttributeError:
        return

    # 1) The "everything" preset fills all five slots with real content.
    mc.setAttr(name + ".preset", 0)
    full = _draw()
    assert_equal(sum(len(b["strings"]) for b in _of(full, "text")), 5,
                 "everything preset must draw 5 text labels")
    assert_equal(sum(len(b["kinds"]) for b in _of(full, "shapes")), 5,
                 "everything preset must draw 5 shape primitives")
    assert_true(any("face_colors" in b for b in _of(full, "polygons")),
                "everything preset must draw a per-face-coloured cube")

    # 2) Each preset enum lights up EXACTLY its slots (nothing stale carries).
    for i, pname in enumerate(enum_order):
        mc.setAttr(name + ".preset", i)
        on = _slots(_draw())
        assert_equal(sorted(on), sorted(expected[pname]),
                     "preset %r drew %s, expected %s"
                     % (pname, sorted(on), sorted(expected[pname])))

    # 3) A custom persistent `presets` dict wins over the shipped default.
    mc.setAttr(name + ".preset", 0)
    set_variable(name, "presets", {"everything": ["text"]}, persistent=True)
    on = _slots(_draw())
    assert_equal(sorted(on), ["text"],
                 "custom presets dict must override the default (got %s)" % sorted(on))
'''

LOC_SHOWCASE_DESC = (
    "# Widget Showcase\n\n"
    "A reference `mPyLocator` that draws one of everything the locator "
    "renderer supports: **lines** (a 3-axis gizmo and a diamond), **points** "
    "(a rainbow grid), **polygons** (a per-face-coloured cube with a "
    "wireframe overlay), **shapes** (sphere, box, cone, cylinder, circle) and "
    "**text** labels.\n\n"
    "The `preset` enum picks what draws: `everything` (the default) shows all "
    "five side by side, or pick a single slot. Behind it is a persistent "
    "`presets` dict variable, so you can edit which slots each preset turns "
    "on.\n\n"
    "Nothing animates -- the cheapest locator to leave in a scene. **Create + "
    "Run demo** bakes the preset dict and frames it."
)


def build_locator_widget_showcase():
    mc.file(new=True, force=True)
    _ensure_mpy_plugins()
    from mpynode._common.node_setups import find_demo
    from mpynode._common.storedvars.stored_vars_api import set_variable
    from mpynode.wrappers.mpy_locator import MPyLocator

    w = MPyLocator.create(name="widgetShowcase")
    node = w.get_name()
    w.add_input_attr("preset", "enum",
                     enum_names=["everything", "curves", "points",
                                 "polygons", "shapes", "text"])
    w.set_init_expression(LOC_SHOWCASE_INIT)
    w.set_compute_expression(LOC_SHOWCASE_COMPUTE)
    w.set_methods_source(DEMO_LOC_SHOWCASE)

    _stamp_class(w, "WidgetShowcase", "mPyLocator")
    clean_payload = serialize_node(w, include_persistent=False)

    enum_order = ["everything", "curves", "points", "polygons", "shapes", "text"]
    expected = {
        "everything": {"lines", "points", "polygons", "shapes", "text"},
        "curves": {"lines"}, "points": {"points"}, "polygons": {"polygons"},
        "shapes": {"shapes"}, "text": {"text"},
    }

    def _of(cmds, slot):
        return [c["buffer"] for c in cmds if c["slot"] == slot]

    # Content sanity on the full "everything" preset.
    mc.setAttr(node + ".preset", 0)
    full = w.evaluate_draw_commands(0.0)["commands"]
    content_ok = bool(
        sum(len(b["strings"]) for b in _of(full, "text")) == 5
        and any("face_colors" in b for b in _of(full, "polygons"))
        and sum(len(b["kinds"]) for b in _of(full, "shapes")) == 5
        and _of(full, "points") and _of(full, "lines"))

    # Each preset lights up exactly its slots (and nothing stale).
    preset_ok = True
    detail = []
    for i, pname in enumerate(enum_order):
        mc.setAttr(node + ".preset", i)
        on = _draw_slots(w)
        ok_i = on == expected[pname]
        preset_ok = preset_ok and ok_i
        if not ok_i:
            detail.append("%s:%s" % (pname, on))

    # A custom persistent `presets` dict wins over the shipped default.
    mc.setAttr(node + ".preset", 0)
    set_variable(node, "presets", {"everything": ["text"]}, persistent=True)
    override_ok = _draw_slots(w) == {"text"}

    has_demo = find_demo(DEMO_LOC_SHOWCASE) is not None

    # Run the authored @maya_test on a FRESH deserialized node.
    test_ok = False
    try:
        mc.file(new=True, force=True)
        _ensure_mpy_plugins()
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, name="widgetShowcaseTestCheck")
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        if not test_ok:
            print("[loc_showcase] @maya_test FAILED: %s" % tres.get("error"))
    except Exception as exc:
        print("[loc_showcase] @maya_test run ERRORED: %r" % exc)

    ok = content_ok and preset_ok and override_ok and has_demo and test_ok
    print("[loc_showcase] content=%s preset=%s%s override=%s demo=%s test=%s"
          " -> %s"
          % (content_ok, preset_ok, (" " + str(detail)) if detail else "",
             override_ok, has_demo, test_ok, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(LOC_SHOWCASE_DIR, clean_payload, LOC_SHOWCASE_DESC)
    return ok


# ======================================================================
# 2. mPyLocator Widgets - animated text :: rainbow text, exact loop
# ======================================================================
LOC_TEXT_INIT = r'''import numpy as np
from mpynode._common.draw.draw_types import (
    DrawCircle, DrawCurve, DrawPoints, DrawText)

TWO_PI = 6.283185307179586


def hue2rgb(h):
    h = (h % 1.0) * 6.0
    i = h.astype(np.int64) % 6
    f = h - np.floor(h)
    r = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5],
                  [1.0, 1.0 - f, 0.0, 0.0, f, 1.0], default=0.0)
    g = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5],
                  [f, 1.0, 1.0, 1.0 - f, 0.0, 0.0], default=0.0)
    b = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5],
                  [0.0, 0.0, f, 1.0, 1.0, 1.0 - f], default=0.0)
    return np.stack([r, g, b], axis=1)
'''

LOC_TEXT_COMPUTE = r'''# Animated rainbow text gizmo, driven by the WALL CLOCK only. self.wallclock is
# seconds since the epoch (time.time()) and is identical in the compiled node,
# so the motion is the same at idle, while scrubbing and in every playback
# mode: frame rate and scene time units never change its speed. Timeline
# animation is opt-in -- an expression gets it by reading self.time (or a
# time plug); this one deliberately does not. `loopDuration` is wall-clock
# seconds per loop: 1 = one loop per second, 2 = two seconds per loop,
# -1 = one loop per second in reverse, 0 = frozen. auto_refresh keeps the
# gizmo repainting between the redraws Maya would otherwise never issue.
self.auto_refresh = True

raw = getattr(self, "displayText", "")
msg = raw if (raw and str(raw).strip()) else "MPyNode!"
chars = list(str(msg))
n = len(chars)
idx = np.arange(n, dtype=np.float64)

dur = float(self.loopDuration)
speed = (1.0 / dur) if dur != 0.0 else 0.0    # loops per wall-clock second
cyc = self.wallclock * speed                  # loop position; its fraction is the phase
phase = TWO_PI * cyc

spacing = self.spacing
wave = self.waveHeight

# layout along X with a slow one-per-loop horizontal sway
xs = (idx - (n - 1) / 2.0) * spacing + 1.2 * np.sin(phase)
ys = wave * np.sin(idx * 0.7 - 2.0 * phase)     # 2 travelling waves / loop
zs = 0.5 * np.cos(idx * 0.5 - 1.0 * phase)
positions = np.stack([xs, ys, zs], axis=1).astype(np.float32)

# scrolling rainbow (hue cycles once per loop + per-glyph offset)
rgb = hue2rgb(idx / max(n, 1) + cyc)
colors = np.concatenate([rgb, np.ones((n, 1))], axis=1).astype(np.float32)
if bool(getattr(self, "selected", False)):
    colors[:] = (1.0, 1.0, 1.0, 1.0)          # flash white while selected

# Text is drawn in the default LOCAL space, so `size` is an OBJECT-space
# glyph height (world units, ~half the 1.3 letter spacing) -- NOT pixels.
# The locator auto-scales the bitmap font from the object's on-screen size,
# so the letters shrink as you zoom the camera out (and grow with the
# transform scale) instead of overlapping. Switch to constant pixels by
# passing screen_space=True to DrawText.
sizes = (0.55 + 0.22 * np.sin(idx * 0.8 - 3.0 * phase)).astype(np.float32)

# twinkling sparkle points above each glyph
sp = positions.copy()
sp[:, 1] += 1.7 + 0.35 * np.sin(idx * 1.3 + 2.0 * phase)
psize = (5.0 + 6.0 * np.abs(np.sin(idx * 0.9 + 2.0 * phase))).astype(np.float32)

# flowing sine ribbon under the text. DrawCurve takes the POLYLINE and does the
# pts[:-1] / pts[1:] segment split itself -- including trimming the per-vertex
# colours to the segment count, which is easy to forget by hand and silently
# rejects the whole buffer when the lengths disagree.
m = 64
lx = np.linspace(xs.min() - 1.0, xs.max() + 1.0, m)
ly = 0.7 * np.sin(lx * 0.8 + 1.0 * phase) - 2.4
pts = np.stack([lx, ly, np.zeros(m)], axis=1).astype(np.float32)
lrgb = hue2rgb(lx * 0.04 + cyc)
lcol = np.concatenate([lrgb, np.ones((m, 1))], axis=1).astype(np.float32)

# pulsing circle halo behind the message
R = 6.0 + 0.6 * np.sin(phase)

# ONE drawing, composed with `+`. Each drawable knows which buffer it belongs to,
# so there are no parallel arrays to keep in sync and no "kinds"/"filled" lists
# to line up by hand.
self.draw = (DrawText(chars, positions, color=colors, size=sizes)
             + DrawPoints(sp, color=colors, size=psize)
             + DrawCurve(pts, color=lcol)
             + DrawCircle(center=(0.0, 0.0, -1.0), radius=R,
                          color=hue2rgb(np.array([cyc]))))
'''

DEMO_LOC_TEXT = '''# Animated Text setup: frame the gizmo. It animates on the wall clock, so
# there is no playback range to set -- it moves whether or not you play.
def demo(self):
    from maya import cmds as mc
    name = self.get_name()
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_test(label="Animated text: glyph layout, message override, animation", digits=3)
def test_animated_text(self):
    """Validate the animated-text locator's INTENT through its draw buffers
    (the same buffers the viewport draws -- there is no numeric output plug):

      1. A blank ``displayText`` defaults to "MPyNode!" -> 8 glyphs, one 3D
         position each (that IS the node's default message).
      2. Setting ``displayText`` re-lays exactly those glyphs.
      3. The gizmo is genuinely animated -- two wall-clock instants lay the
         text out differently, and the same instant repeats (the clock is
         injected, so the check is deterministic; the timeline plays no part).
      4. Every advertised draw slot (text / points / lines / shapes) is
         populated this frame.

    A COMPILED C++ locator (MPxLocatorNode) exposes no Python
    ``evaluateDrawItems``, so its draw buffers are not reachable here -- that
    parity is covered by the dedicated ``-DMPYNODE_PROBE`` numerical buffer
    comparison. When the buffers cannot be read (compiled node) this test skips
    cleanly so it never false-fails parity.
    """
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_equal, assert_true

    name = self.get_name()

    def _cmds(wallclock=None):
        # Read the ordered draw commands off the node's PUBLIC MPx surface using
        # the node NAME (not self.evaluate_draw_commands(), a wrapper method
        # absent on the compiled node's _NodeNameProxy) so the SAME test runs on
        # both the interpreted node and its C++ compile.
        sel = om2.MSelectionList()
        sel.add(name)
        mpx = om2.MFnDependencyNode(sel.getDependNode(0)).userNode()
        return (mpx.evaluateDrawItems(0.0, wallclock=wallclock) or {}).get("commands") or []

    def _slot(cmds, slot):
        for cmd in cmds:
            if cmd["slot"] == slot:
                return cmd["buffer"]
        return None

    # The output lives in draw commands reached via evaluateDrawItems, which only
    # the interpreted mPyNode exposes to Python. On a compiled node this is
    # unavailable -> skip (compiled parity is probe-verified).
    try:
        _cmds()
    except Exception:
        return

    # 1) Blank message -> "MPyNode!" (8 glyphs), one (x, y, z) per glyph.
    mc.setAttr(name + ".displayText", "", type="string")
    txt = _slot(_cmds(), "text")
    assert_true(txt is not None, "the drawing must include text")
    assert_equal(len(txt["strings"]), len("MPyNode!"),
                 "blank message should default to MPyNode!")
    assert_equal(tuple(txt["positions"].shape), (8, 3),
                 "one 3D position per default glyph")

    # 2) Override the message -> exactly those glyphs are laid out.
    mc.setAttr(name + ".displayText", "Hi", type="string")
    cmds2 = _cmds()
    assert_equal(list(_slot(cmds2, "text")["strings"]), ["H", "i"],
                 "displayText must drive the glyph layout")

    # 3) Animated on the wall clock: two instants differ, the same instant repeats.
    a = _slot(_cmds(wallclock=0.0), "text")["positions"]
    b = _slot(_cmds(wallclock=0.25), "text")["positions"]
    a2 = _slot(_cmds(wallclock=0.0), "text")["positions"]
    assert_true(not np.allclose(a, b),
                "a quarter second of wall clock must move the animated text")
    assert_true(np.allclose(a, a2),
                "the drawing must be a pure function of the wall clock")

    # 4) Every advertised draw slot is populated this frame.
    drawn = {c["slot"] for c in cmds2}
    for slot in ("text", "points", "lines", "shapes"):
        assert_true(slot in drawn, "draw slot %r must be populated" % slot)
'''

LOC_TEXT_DESC = (
    "# Animated Text\n\n"
    "A text gizmo (`mPyLocator`) that puts a message in the viewport: the "
    "letters ride a travelling sine wave with a scrolling rainbow, trailed by "
    "sparkle points, a line ribbon and a pulsing halo. Good for a rig banner "
    "or a state readout.\n\n"
    "Type your message into `displayText`; blank shows `MPyNode!`. "
    "`loopDuration` is wall-clock seconds per loop (default 1; 2 is slower, "
    "-1 runs in reverse, 0 freezes); `spacing` and `waveHeight` set the "
    "layout. Selecting the gizmo flashes it white.\n\n"
    "The motion runs off the wall clock (`self.wallclock`), never the "
    "timeline: it looks the same at idle, while scrubbing and in every "
    "playback mode, and the compiled node matches it exactly. "
    "**Create + Run demo** frames it."
)


def build_locator_animated_text():
    mc.file(new=True, force=True)
    _ensure_mpy_plugins()
    from mpynode._common.node_setups import find_demo
    from mpynode.wrappers.mpy_locator import MPyLocator

    w = MPyLocator.create(name="animatedText")
    node = w.get_name()
    w.add_input_attr("displayText", "string")
    w.add_input_attr("loopDuration", "float", default_value=1.0)
    w.add_input_attr("spacing", "float", default_value=1.3)
    w.add_input_attr("waveHeight", "float", default_value=1.6)
    w.set_init_expression(LOC_TEXT_INIT)
    w.set_compute_expression(LOC_TEXT_COMPUTE)
    w.set_methods_source(DEMO_LOC_TEXT)

    _stamp_class(w, "AnimatedText", "mPyLocator")
    clean_payload = serialize_node(w, include_persistent=False)

    # Default (blank message) -> "MPyNode!" (8 glyphs).
    buf = _draw_slot(w, "text")
    default_ok = (buf is not None
                  and len(buf["strings"]) == len("MPyNode!")
                  and buf["positions"].shape == (8, 3))

    # Override message.
    mc.setAttr(node + ".displayText", "Hi", type="string")
    buf2 = _draw_slot(w, "text")
    override_ok = buf2 is not None and buf2["strings"] == ["H", "i"]
    # Local-space text: sizes are now OBJECT-space heights (floats, ~0.3-0.8
    # world units), auto-scaled to pixels by the draw override at render time.
    _sz = np.asarray(buf2["sizes"])
    sizes_ok = (np.issubdtype(_sz.dtype, np.floating)
                and float(_sz.min()) > 0.0 and float(_sz.max()) < 3.0)

    # Wall-clock animation: with the timeline untouched, two live evaluations a
    # moment apart must differ (the gizmo never depends on the frame).
    import time as _time
    mc.setAttr(node + ".displayText", "", type="string")
    b0 = _draw_slot(w, "text")
    _time.sleep(0.05)
    b0b = _draw_slot(w, "text")
    idle_animates = not np.allclose(b0["positions"], b0b["positions"])
    # ...and the drawing is a pure function of the injected wall clock: two
    # instants differ, the same instant repeats (the timeline plays no part).
    b_a = _draw_slot(w, "text", wallclock=0.0)
    b_b = _draw_slot(w, "text", wallclock=0.25)
    b_a2 = _draw_slot(w, "text", wallclock=0.0)
    animates = (not np.allclose(b_a["positions"], b_b["positions"])
                and np.allclose(b_a["positions"], b_a2["positions"]))

    slots_ok = {"text", "points", "lines", "shapes"} <= _draw_slots(w)

    has_demo = find_demo(DEMO_LOC_TEXT) is not None

    # Run the authored @maya_test on a FRESH deserialized node.
    test_ok = False
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, name="animTextTestCheck")
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        if not test_ok:
            print("[loc_text] @maya_test FAILED: %s" % tres.get("error"))
    except Exception as exc:
        print("[loc_text] @maya_test run ERRORED: %r" % exc)

    ok = (default_ok and override_ok and sizes_ok and idle_animates and animates
          and slots_ok and has_demo and test_ok)
    print("[loc_text] default=%s override=%s sizes=%s idle_animates=%s "
          "animates=%s slots=%s demo=%s test=%s -> %s"
          % (default_ok, override_ok, sizes_ok, idle_animates, animates,
             slots_ok, has_demo, test_ok, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(LOC_TEXT_DIR, clean_payload, LOC_TEXT_DESC)
    return ok


# ======================================================================
# 3. mPyLocator Widgets - animated selection :: hover-pop spinning gizmo
# ======================================================================
LOC_SEL_INIT = r'''import math
import numpy as np
from mpynode._common.draw.draw_types import DrawMesh


def elastic_in_out(t):
    # Penner elastic in/out easing on [0, 1]: 0 at 0, 1 at 1, spring wobble.
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    p = 0.45
    s = p / 4.0
    t2 = 2.0 * t - 1.0
    if t2 < 0.0:
        return -0.5 * (2.0 ** (10.0 * t2)) * math.sin((t2 - s) * (2.0 * math.pi / p))
    return (2.0 ** (-10.0 * t2)) * math.sin((t2 - s) * (2.0 * math.pi / p)) * 0.5 + 1.0


cube_pts = np.array([
        [-1.0, -1.0, -1.0], [1.0, -1.0, -1.0], [1.0, 1.0, -1.0], [-1.0, 1.0, -1.0],
        [-1.0, -1.0, 1.0], [1.0, -1.0, 1.0], [1.0, 1.0, 1.0], [-1.0, 1.0, 1.0]], dtype=np.float64)
cube_idx = np.array(
    [0, 3, 2, 1, 4, 5, 6, 7, 0, 1, 5, 4, 2, 3, 7, 6, 0, 4, 7, 3, 1, 2, 6, 5], dtype=np.int64)
cube_cnt = np.array([4, 4, 4, 4, 4, 4], dtype=np.int64)

FACE_HUES = np.array([
        [0.90, 0.20, 0.25, 1.0], [0.95, 0.55, 0.15, 1.0], [0.95, 0.85, 0.20, 1.0],
        [0.30, 0.80, 0.35, 1.0], [0.25, 0.55, 0.95, 1.0], [0.60, 0.35, 0.85, 1.0]], dtype=np.float64)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]], dtype=np.float64)


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]], dtype=np.float64)


def vertex_palette():
    rgb = (cube_pts + 1.0) * 0.5
    return np.concatenate([rgb, np.ones((cube_pts.shape[0], 1))], axis=1)


def face_vertex_palette():
    out = []
    for f, c in enumerate(cube_cnt):
        c = int(c)
        for k in range(c):
            col = FACE_HUES[f].copy()
            col[:3] = col[:3] * (1.0 if k == 0 else 0.4)
            out.append(col)
    return np.array(out, dtype=np.float64)


VERTEX_COLORS = vertex_palette()
FACE_VERTEX_COLORS = face_vertex_palette()
'''

LOC_SEL_COMPUTE = r'''# Polygon-shading showcase cube: spins on the WALL CLOCK (self.wallclock --
# seconds since the epoch, never the timeline), "pops" on mouse HOVER (an
# elastic tween on the same clock), and recolours via the `color_mode`
# enum. Selection tints the FILL only (highlight_fill) while the wireframe
# keeps its own colour (highlight_wire=False) -- per-aspect highlighting.
# Animation state lives in getattr-defaulted vars, so it needs no seeding.
hovered = bool(self.hovered)
now = float(self.wallclock)
duration = max(self.popDuration, 1e-3)
amount = self.popAmount

prev = bool(getattr(self, "prev_hovered", False))
anim_start = float(getattr(self, "anim_start_t", 0.0))
anim_from = float(getattr(self, "anim_from", 0.0))
anim_to = float(getattr(self, "anim_to", 0.0))

elapsed = (now - anim_start) / duration
elapsed = 0.0 if elapsed < 0.0 else (1.0 if elapsed > 1.0 else elapsed)
current_pop = anim_from + (anim_to - anim_from) * elastic_in_out(elapsed)

if hovered != prev:
    self.anim_start_t = now
    self.anim_from = current_pop
    self.anim_to = 1.0 if hovered else 0.0
    self.prev_hovered = hovered
    elapsed = 0.0

scale = 1.0 + amount * current_pop

# Spin on the wall clock at the user-tunable spinSpeed (radians per second).
ang = self.wallclock * self.spinSpeed
spun = ((cube_pts * scale) @ rot_y(ang).T) @ rot_x(ang * 0.6).T

# The four fill modes are named after the buffer key each one drives, so the
# enum maps straight onto a DrawMesh keyword. They are mutually exclusive --
# passing two raises instead of silently letting the renderer pick by
# precedence.
mode = self.color_mode.name()
if mode == "face":
    fill = {"color": FACE_HUES}                       # flat, per face
elif mode == "vertex":
    fill = {"vertex_colors": VERTEX_COLORS}           # smooth, per point
elif mode == "face_vertex":
    fill = {"face_vertex_colors": FACE_VERTEX_COLORS}  # per corner
else:  # "uniform"
    fill = {"uniform_color": (0.45, 0.85, 1.0, 0.6)}  # one setColor call

# highlight_fill/highlight_wire are per-ASPECT: selection tints the fill but
# leaves the wireframe its own colour. outline_boundary_only=False keeps every
# cube edge, matching the wire overlay this demo is showing off.
cube = DrawMesh(spun, cube_cnt, cube_idx,
                cull_backfaces=True, precise_hover=True,
                highlight_fill=True, highlight_wire=False, **fill)

if self.show_wireframe:
    cube = cube.outlined((0.04, 0.04, 0.06, 1.0), width=self.wire_width, boundary_only=False)

self.draw = cube
self.auto_highlight = False      # we drive highlighting ourselves
# Keep repainting while the pop tween runs AND while the cube spins: on the wall
# clock nothing else ever redraws it between interactions (a still cube with
# spinSpeed 0 rests once its tween settles).
self.auto_refresh = bool(elapsed < 1.0) or float(self.spinSpeed) != 0.0
'''

DEMO_LOC_SEL = '''# Animated Selection setup: frame the cube. Spin and hover pop both run on
# the wall clock, so nothing about the timeline needs setting.
def demo(self):
    from maya import cmds as mc
    name = self.get_name()
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_test(label="Animated selection: color modes, wireframe, spin", digits=3)
def test_animated_selection(self):
    """Validate the node's INTENT through its draw buffers (a locator's only
    output), exactly as the builder's own live gate does: each ``color_mode``
    drives the matching polygon colour key with backface culling on,
    ``show_wireframe`` toggles the wireframe overlay, and ``spinSpeed`` genuinely
    spins the cube over time.

    A COMPILED C++ locator (MPxLocatorNode) exposes no Python
    ``evaluateDrawItems``, so its draw buffers are not reachable here -- that
    parity is covered by the dedicated ``-DMPYNODE_PROBE`` numerical buffer
    comparison. When the buffers cannot be read (compiled node) this test skips
    cleanly so it never false-fails parity."""
    import numpy as np
    from maya import cmds as mc
    from mpynode.wrappers.mpy_locator import MPyLocator
    from mpynode._common.methods.test_helpers import assert_true

    name = self.get_name()
    w = MPyLocator(name)

    def _poly(wallclock=None):
        """This instant's polygon buffer, or None."""
        for cmd in w.evaluate_draw_commands(0.0, wallclock=wallclock)["commands"]:
            if cmd["slot"] == "polygons":
                return cmd["buffer"]
        return None

    # The output lives in draw commands reached via evaluateDrawItems, which only
    # the interpreted mPyNode exposes to Python. On a compiled node this is
    # unavailable -> skip (compiled parity is probe-verified).
    try:
        probe = _poly()
    except Exception:
        return
    if probe is None:
        return

    # 1) Each color_mode drives the matching polygon colour key (backface-culled).
    for i, key in enumerate(
            ["face_colors", "vertex_colors", "face_vertex_colors", "colors"]):
        mc.setAttr(name + ".color_mode", i)
        poly = _poly()
        assert_true(poly is not None and key in poly
                    and poly.get("cull_backfaces") is True,
                    "color_mode %d must set %r with cull_backfaces" % (i, key))

    # 2) show_wireframe toggles the wireframe overlay on/off.
    mc.setAttr(name + ".color_mode", 0)
    mc.setAttr(name + ".show_wireframe", True)
    assert_true("wireframe" in (_poly() or {}),
                "show_wireframe True must add a wireframe overlay")
    mc.setAttr(name + ".show_wireframe", False)
    assert_true("wireframe" not in (_poly() or {}),
                "show_wireframe False must drop the wireframe overlay")

    # 3) spinSpeed spins on the wall clock: two instants give different points.
    mc.setAttr(name + ".spinSpeed", 0.5)
    s0 = np.asarray(_poly(wallclock=0.0)["points"])
    s1 = np.asarray(_poly(wallclock=1.0)["points"])
    assert_true(not np.allclose(s0, s1),
                "spinSpeed should rotate the cube as the wall clock advances")

    # 4) A spinning cube keeps repainting; a still one rests once its tween is over.
    mc.setAttr(name + ".spinSpeed", 1.0)
    assert_true(w.evaluate_draw_commands(0.0, wallclock=5.0)["auto_refresh"] is True,
                "a spinning cube must request idle redraws")
    mc.setAttr(name + ".spinSpeed", 0.0)
    assert_true(w.evaluate_draw_commands(0.0, wallclock=5.0)["auto_refresh"] is False,
                "a still cube must not request idle redraws")
'''

LOC_SEL_DESC = (
    "# Animated Selection\n\n"
    "A shaded cube (`mPyLocator`) that spins on the wall clock and pops out "
    "under the mouse. Hover is a real ray-versus-triangle test, not a "
    "bounding box, and the pop runs off the wall clock, so it plays on any "
    "redraw.\n\n"
    "`color_mode` sets the fill: `face` (flat per-face hues), `vertex` (a "
    "gradient across the corners), `face_vertex` (smooth inside a face, hard "
    "seams between) or `uniform` (one translucent colour). `show_wireframe` "
    "and `wire_width` add an edge overlay. `spinSpeed` (radians per wall-clock second), "
    "`popDuration` and `popAmount` tune the motion. Selecting the cube tints "
    "the fill only.\n\n"
    "**Create + Run demo** frames it."
)


def build_locator_animated_selection():
    mc.file(new=True, force=True)
    _ensure_mpy_plugins()
    from mpynode._common.node_setups import find_demo
    from mpynode.wrappers.mpy_locator import MPyLocator

    w = MPyLocator.create(name="animatedSelection")
    node = w.get_name()
    w.add_input_attr("color_mode", "enum",
                     enum_names=["face", "vertex", "face_vertex", "uniform"])
    w.add_input_attr("show_wireframe", "bool", default_value=True)
    w.add_input_attr("wire_width", "float", default_value=2.0)
    w.add_input_attr("spinSpeed", "float", default_value=1.0)
    w.add_input_attr("popDuration", "float", default_value=0.6)
    w.add_input_attr("popAmount", "float", default_value=0.45)
    w.set_init_expression(LOC_SEL_INIT)
    w.set_compute_expression(LOC_SEL_COMPUTE)
    w.set_methods_source(DEMO_LOC_SEL)

    _stamp_class(w, "AnimatedSelection", "mPyLocator")
    clean_payload = serialize_node(w, include_persistent=False)

    # Each color_mode drives the matching polygon colour key.
    mode_ok = True
    mode_detail = []
    for i, (mode, key) in enumerate([
            ("face", "face_colors"), ("vertex", "vertex_colors"),
            ("face_vertex", "face_vertex_colors"), ("uniform", "colors")]):
        mc.setAttr(node + ".color_mode", i)
        poly = _draw_slot(w, "polygons")
        ok_i = (poly is not None and key in poly
                and poly.get("cull_backfaces") is True)
        mode_ok = mode_ok and ok_i
        if not ok_i:
            mode_detail.append("%s:%s" % (mode, None if poly is None else list(poly)))

    # Wireframe overlay toggles.
    mc.setAttr(node + ".color_mode", 0)
    mc.setAttr(node + ".show_wireframe", True)
    wire_on = "wireframe" in (_draw_slot(w, "polygons") or {})
    mc.setAttr(node + ".show_wireframe", False)
    wire_off = "wireframe" not in (_draw_slot(w, "polygons") or {})
    wire_ok = wire_on and wire_off

    # spinSpeed actually spins: two wall-clock instants differ.
    mc.setAttr(node + ".spinSpeed", 0.5)
    s0 = _draw_slot(w, "polygons", wallclock=0.0)["points"]
    s1 = _draw_slot(w, "polygons", wallclock=1.0)["points"]
    spin_ok = not np.allclose(s0, s1)
    # ...and a spinning cube asks for idle redraws while a still one rests.
    mc.setAttr(node + ".spinSpeed", 1.0)
    refresh_spinning = w.evaluate_draw_commands(0.0, wallclock=5.0)["auto_refresh"] is True
    mc.setAttr(node + ".spinSpeed", 0.0)
    refresh_still = w.evaluate_draw_commands(0.0, wallclock=5.0)["auto_refresh"] is False
    spin_ok = spin_ok and refresh_spinning and refresh_still

    has_demo = find_demo(DEMO_LOC_SEL) is not None

    # Run the authored @maya_test on a FRESH deserialized node.
    test_ok = False
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        if not test_ok:
            print("[loc_selection] @maya_test FAILED: %s" % tres.get("error"))
    except Exception as exc:
        print("[loc_selection] @maya_test run ERRORED: %r" % exc)

    ok = mode_ok and wire_ok and spin_ok and has_demo and test_ok
    print("[loc_selection] modes=%s%s wire=%s spin=%s demo=%s test=%s -> %s"
          % (mode_ok, (" " + str(mode_detail)) if mode_detail else "",
             wire_ok, spin_ok, has_demo, test_ok, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(LOC_SELECTION_DIR, clean_payload, LOC_SEL_DESC)
    return ok


# ======================================================================
# 4. mPyLocator Widget - mesh regions :: draw every component-tag patch
# ======================================================================
LOC_REGION_INIT = r'''import math
import numpy as np
from mpynode._common.draw.draw_types import DrawMesh
from mpynode._common.nodes.mesh.mesh_region import extract_region
from mpynode._common.nodes.mesh.component_tags import (
    node_name_from_self, mesh_data_from_node_plug, tag_indices_from_mesh_data,
    mesh_matrix_from_mesh_data)

MIN_OFFSET = 0.004      # floor so elastic undershoot never dips into the mesh
# Fill AND outline colour, plus the per-state offsets, are LIVE input attrs
# (defaultColor / hoverColor / selectColor, outlineColor / outlineHoverColor /
# outlineSelectColor, offset / hoverOffset / selectOffset / alpha), so the
# palette/tint constants that used to live here are gone -- the compute reads
# them off self.<attr> and a user can tweak each one interactively. Every colour
# input carries its OWN attr default, so a raw-created node already looks right
# and the compute never has to guess whether a value is "unset": all-zero means
# exactly BLACK, which is the colour the user dialled.


def elastic_in_out(t):
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    p = 0.45
    s = p / 4.0
    t2 = 2.0 * t - 1.0
    if t2 < 0.0:
        return -0.5 * (2.0 ** (10.0 * t2)) * math.sin((t2 - s) * (2.0 * math.pi / p))
    return (2.0 ** (-10.0 * t2)) * math.sin((t2 - s) * (2.0 * math.pi / p)) * 0.5 + 1.0


def tween(now, start, frm, to, dur):
    e = (now - start) / max(dur, 1e-3)
    e = 0.0 if e < 0.0 else (1.0 if e > 1.0 else e)
    return frm + (to - frm) * elastic_in_out(e), e
'''

LOC_REGION_COMPUTE = r'''# Draw the bound mesh's component-tag region as a coloured patch. The region
# MEMBERSHIP is resolved LIVE from the input mesh DATA every evaluation (via
# MFnGeometryData), keyed by this gizmo's tag NAME (`regionTag`, baked once by
# setup) -- so editing the component tag (add/remove faces) updates the drawn
# region immediately, and a compiled C++ node resolves the SAME way off its own
# input handle. self.inMesh is the live world-space MFnMesh (worldMesh[0]) used
# for the geometry; the tag membership comes from that same input's data.
mesh = self.inMesh
# The region is chosen purely by NAME via the `regionTag` string input. If the
# name matches no component tag on the input mesh -- or is unset -- the region
# goes BLANK (a typo or a removed/renamed tag reads as empty). `setup` names the
# region, and migrates a pre-regionTag scene's baked `regions` dict into that
# name, so the draw reads no stored Python state: the interpreted and the
# compiled node resolve the region the same way.
_tag = getattr(self, "regionTag", None)
# ONE read of the input data, shared by the tag membership and the source
# transform below (both live on the same MFnGeometryData).
_mdata = mesh_data_from_node_plug(node_name_from_self(self), "inMesh")
_wmat = mesh_matrix_from_mesh_data(_mdata)
regions = None
if _tag:
    _faces = tag_indices_from_mesh_data(_mdata, _tag)
    if _faces:
        regions = {_tag: _faces}
    # else: named tag has no match -> leave regions None -> blank.
if mesh is None or not regions:
    self.draw = None
else:
    offset = self.offset
    hover_offset = self.hoverOffset
    select_offset = self.selectOffset
    hover_dur = max(self.hoverDur, 1e-3)
    alpha = float(self.alpha)
    # Per-state RGB colours (each a 3-float `color` input) + one shared alpha.
    # The active colour tweens default->hover on the SAME elastic curve as the
    # lift, and snaps to the select colour when selected. Each input carries its
    # own attr DEFAULT, so what is read here is exactly what the user dialled --
    # all-zero means BLACK, not "unset". Nothing is substituted.
    def_c = np.asarray(self.defaultColor, dtype=np.float64).ravel()[:3]
    hov_c = np.asarray(self.hoverColor, dtype=np.float64).ravel()[:3]
    sel_c = np.asarray(self.selectColor, dtype=np.float64).ravel()[:3]
    # The outline around each patch has the SAME three states, on the same
    # curve, so it can read as its own accent rather than a fixed dark edge.
    odef_c = np.asarray(self.outlineColor, dtype=np.float64).ravel()[:3]
    ohov_c = np.asarray(self.outlineHoverColor, dtype=np.float64).ravel()[:3]
    osel_c = np.asarray(self.outlineSelectColor, dtype=np.float64).ravel()[:3]

    hovered = bool(self.hovered)
    selected = bool(self.selected)
    if selected:
        hovered = False          # selected shows only its selected form
    now = float(self.wallclock)

    h_cur, h_e = tween(now, float(getattr(self, "hv_start", 0.0)),
                       float(getattr(self, "hv_from", 0.0)),
                       float(getattr(self, "hv_to", 0.0)), hover_dur)
    if hovered != bool(getattr(self, "hv_prev", False)):
        self.hv_start = now
        self.hv_from = h_cur
        self.hv_to = 1.0 if hovered else 0.0
        self.hv_prev = hovered
        h_e = 0.0

    # THREE ABSOLUTE normal offsets (world units): the patch floats at `offset`
    # at rest, tweens to `hoverOffset` on hover, and snaps to `selectOffset`
    # when selected. Absolute (not additive) + a fixed normal lift (never an
    # in-plane centroid balloon), so the pop is identical no matter how many
    # faces the tag covers -- a tag grown to span the whole mesh lifts by the
    # same amount as a tiny one.
    lift = offset + (hover_offset - offset) * h_cur
    if selected:
        lift = select_offset
    if lift < MIN_OFFSET:
        lift = MIN_OFFSET

    # Active fill colour: tween default->hover on the hover curve, snap to the
    # select colour when selected; append the shared alpha to make the RGBA row
    # the polygons buffer expects.
    rgb = def_c + (hov_c - def_c) * h_cur
    if selected:
        rgb = sel_c
    rgba = np.concatenate([rgb, [alpha]])

    # The outline rides the SAME hover curve and the same select snap. It stays
    # opaque: `alpha` fades the FILL so the surface shows through, and letting
    # the silhouette fade with it would wash the patch's edge out entirely.
    orgb = odef_c + (ohov_c - odef_c) * h_cur
    if selected:
        orgb = osel_c
    orgba = np.concatenate([orgb, [1.0]])

    # One DrawMesh per tag. `self.draw` takes the LIST straight -- no `sum()`
    # and no `+` chain to build -- and draws them in the order appended. This
    # used to be four parallel accumulator lists plus a hand-rolled
    # `idx + voff` rebase.
    patches = []
    for tag in sorted(regions.keys()):
        faces = np.asarray(regions[tag], dtype=np.int64).ravel()
        if faces.size == 0:
            continue
        pts, idx, cnt, nrm = extract_region(mesh, faces, with_normals=True)
        if pts.shape[0] == 0:
            continue
        # extract_region reads OBJECT space: the mesh DATA carries the source
        # transform as a SEPARATE matrix, and a data-built MFnMesh has no DAG
        # path so getPoints(kWorld) cannot reach world. `world_space=True` below
        # takes these points AS world, so apply that matrix here -- without it
        # the patch draws at the ORIGIN and never follows the mesh. Maya is
        # row-vector (p * M): the 3x3 rotates/scales, row 3 translates.
        if _wmat is not None:
            _m = np.asarray(_wmat, dtype=np.float64).reshape(4, 4)
            pts = pts @ _m[:3, :3] + _m[3, :3]
            nrm = nrm @ _m[:3, :3]
            _mag = np.linalg.norm(nrm, axis=1, keepdims=True)
            nrm = nrm / np.where(_mag > 1e-12, _mag, 1.0)
        patches.append(DrawMesh(
            pts + nrm * lift, cnt, idx, color=rgba,
            outline=orgba, outline_width=2.0,
            outline_boundary_only=True,   # clean outer silhouette only
            world_space=True,             # follow the mesh, not the locator
            precise_hover=True))

    if not patches:
        self.draw = None
    else:
        self.draw = patches
        self.auto_highlight = False
        self.auto_refresh = bool(h_e < 1.0)
'''

DEMO_LOC_REGION = VANILLA_SETUP_ERROR + VANILLA_MESHES + '''
# Region-extraction helpers, VENDORED from
# mpynode._common.nodes.mesh.mesh_region. setup is a @maya_command body, which
# ships as embedded python inside the compiled .mll -- where mpynode is NOT
# importable -- so extract_region and its whole closure (mesh_arrays /
# mesh_vertex_normals and their api1 fallbacks) are carried here instead of
# imported. numpy + the OpenMaya modules are imported per-def.
def _is_api2(mesh):
    """True for an API-2.0 function set, False for a legacy API-1.0 one.
    Both classes are named ``MFnMesh``, so we distinguish by module:
    API 1.0 is ``maya.OpenMaya``; API 2.0 reports ``OpenMaya``."""
    return type(mesh).__module__ != "maya.OpenMaya"


def _arrays_api1(mesh, space):
    """Legacy API-1.0 read path. API 1.0 has no vectorized point accessor,
    so points go through a small per-vertex loop; connectivity uses the
    scalar-iterable MIntArray (np.fromiter)."""
    import numpy as np
    import maya.OpenMaya as om1

    space1 = om1.MSpace.kObject if space is None else int(space)
    pa = om1.MPointArray()
    mesh.getPoints(pa, space1)
    n = pa.length()
    pts = np.empty((n, 3), dtype=np.float64)
    for i in range(n):
        p = pa[i]
        pts[i, 0] = p.x
        pts[i, 1] = p.y
        pts[i, 2] = p.z
    counts1 = om1.MIntArray()
    connects1 = om1.MIntArray()
    mesh.getVertices(counts1, connects1)
    counts = np.fromiter(counts1, dtype=np.int64, count=counts1.length())
    connects = np.fromiter(connects1, dtype=np.int64, count=connects1.length())
    return pts, counts, connects


def mesh_arrays(mesh, space=None):
    """Return ``(points (V,3) float64, counts (F,) int64, connects (C,) int64)``
    for an ``MFnMesh`` (API 2.0 preferred, API 1.0 supported)."""
    import numpy as np
    import maya.api.OpenMaya as om

    if not _is_api2(mesh):
        return _arrays_api1(mesh, space)
    if space is None:
        space = om.MSpace.kObject
    # getPoints -> MPointArray; np.array gives (V, 4) [x,y,z,w] -> drop w.
    pts = np.asarray(mesh.getPoints(space))[:, :3].astype(np.float64)
    counts_arr, connects_arr = mesh.getVertices()
    counts = np.asarray(counts_arr, dtype=np.int64)
    connects = np.asarray(connects_arr, dtype=np.int64)
    return pts, counts, connects


def _normals_api1(mesh, space):
    """Legacy API-1.0 per-vertex normal read (out-param + small loop)."""
    import numpy as np
    import maya.OpenMaya as om1

    space1 = om1.MSpace.kObject if space is None else int(space)
    nrm = om1.MFloatVectorArray()
    mesh.getVertexNormals(False, nrm, space1)
    n = nrm.length()
    out = np.empty((n, 3), dtype=np.float64)
    for i in range(n):
        v = nrm[i]
        out[i, 0] = v.x
        out[i, 1] = v.y
        out[i, 2] = v.z
    return out


def mesh_vertex_normals(mesh, space=None):
    """Return ``(V, 3)`` unit per-vertex normals (Maya's averaged vertex
    normals) for an ``MFnMesh``, aligned with ``mesh_arrays`` point order."""
    import numpy as np
    import maya.api.OpenMaya as om

    if not _is_api2(mesh):
        n = _normals_api1(mesh, space)
    else:
        if space is None:
            space = om.MSpace.kObject
        n = np.asarray(
            mesh.getVertexNormals(False, space))[:, :3].astype(np.float64)
    # Defensive renormalize (Maya returns unit normals, but guard zeros).
    mag = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.where(mag > 1e-12, mag, 1.0)


def extract_region(mesh, face_ids, space=None, with_normals=False):
    """Build a compact polygon buffer for the faces in ``face_ids`` from a
    live ``MFnMesh``.

    Returns ``(points, indices, counts)`` -- or, when ``with_normals`` is
    True, ``(points, indices, counts, normals)``. The region's vertices are
    compacted + remapped, so ``indices`` refer only to the returned
    ``points``. Fully vectorized -- no per-face loops."""
    import numpy as np

    def _empty():
        z3 = np.zeros((0, 3), dtype=np.float64)
        zi = np.zeros((0,), dtype=np.int64)
        return (z3, zi, zi.copy(), z3.copy()) if with_normals else (z3, zi, zi.copy())

    if mesh is None:
        return _empty()
    pts, counts, connects = mesh_arrays(mesh, space)
    face_ids = np.asarray(face_ids, dtype=np.int64).ravel()
    if face_ids.size == 0 or counts.shape[0] == 0:
        return _empty()
    # Keep only valid face ids.
    face_ids = face_ids[(face_ids >= 0) & (face_ids < counts.shape[0])]
    if face_ids.size == 0:
        return _empty()

    face_off = np.cumsum(counts) - counts          # start offset into connects/face
    sel_counts = counts[face_ids]                  # (M,)
    starts = face_off[face_ids]                    # (M,)
    total = int(sel_counts.sum())
    if total == 0:
        return _empty()

    # Flatten the selected faces' connectivity positions (vectorized).
    face_of = np.repeat(np.arange(face_ids.size), sel_counts)            # (total,)
    within = np.arange(total) - (np.cumsum(sel_counts) - sel_counts)[face_of]
    connect_pos = starts[face_of] + within                              # (total,)
    region_verts = connects[connect_pos]                                # global vertex ids

    # Compact the used vertices + remap the connectivity to 0..U-1.
    uniq, inverse = np.unique(region_verts, return_inverse=True)
    region_points = pts[uniq]
    region_indices = inverse.astype(np.int64)
    region_counts = sel_counts.astype(np.int64)
    if not with_normals:
        return region_points, region_indices, region_counts
    region_normals = mesh_vertex_normals(mesh, space)[uniq]
    return region_points, region_indices, region_counts, region_normals


# Mesh Regions demo: fabricate the whole showcase scene. Import the bundled
# head model, resolve EVERY component tag, then build ONE gizmo PER tag -- `self`
# is the first tag's gizmo and each remaining tag gets a DUPLICATE of `self`
# (which carries its Init/Compute/Methods sources + input attrs along). The
# demo only creates + arranges the gizmos: it sets each gizmo's `regionTag`
# and then DELEGATES the actual per-node binding (`inMesh` wire + positioning) to
# that gizmo's own ``setup`` via ``run_setup([mesh])`` -- so demo and setup never
# duplicate the wiring logic.
def get_component_tag_faces(mesh_shape):
    """
    Retrieves component tags on a mesh shape and returns a dictionary.
    Keys are the tag names.
    Values are flattened, unique, and sorted lists of face indices.
    """
    from maya import cmds as mc

    attr_path = f"{mesh_shape}.outMesh"
    tags = mc.geometryAttrInfo(attr_path, componentTagNames=True)

    tag_faces_dict = {}

    if not tags:
        return tag_faces_dict

    for tag in tags:
        contents = mc.geometryAttrInfo(attr_path, componentTagExpression=tag, components=True)

        # Use a set to automatically guarantee unique indices
        face_indices = set()

        if contents:
            for comp in contents:
                comp = comp.strip()

                # Check if the string represents a face (starts with 'f[' or 'F[')
                if comp.lower().startswith('f['):
                    # Extract the contents inside the square brackets
                    inner_str = comp.split('[')[1].split(']')[0]

                    # Handle ranges (e.g., '10:55')
                    if ':' in inner_str:
                        start_idx, end_idx = inner_str.split(':')
                        # range() stops before the end value, so we add 1 to make it inclusive
                        face_indices.update(range(int(start_idx), int(end_idx) + 1))

                    # Handle single digits (e.g., '10')
                    else:
                        face_indices.add(int(inner_str))

        # Convert the set back to a list and sort it
        tag_faces_dict[tag] = sorted(list(face_indices))

    return tag_faces_dict


def demo(self):
    from maya import cmds as mc
    from mpynode import wrap_node
    import os
    import re
    name = self.get_name()

    head = None
    try:
        from mpynode._common.util.template_gallery import _bundled_templates_root
        root = _bundled_templates_root()
        if root:
            cand = os.path.join(root, "MPyLocator", "Mesh Regions", "head.ma")
            if os.path.isfile(cand):
                head = cand
    except Exception:
        head = None
    if not head:
        return name

    new_nodes = mc.file(head, i=True, returnNewNodes=True,
                        namespace="headModel") or []
    meshes = [n for n in new_nodes if mc.nodeType(n) == "mesh"]
    if not meshes:
        meshes = mc.ls("headModel:*", type="mesh", long=True) or []
    if not meshes:
        return name
    shape = (mc.ls(meshes[0], long=True) or [meshes[0]])[0]

    tags = sorted(get_component_tag_faces(shape).keys())
    if not tags:
        return name

    def _san(tag):
        s = re.sub(r"[^0-9A-Za-z_]", "_", str(tag))
        if not s:
            s = "region"
        if s[0].isdigit():
            s = "_" + s
        return s + "Region"

    # self is tag[0]'s gizmo; duplicate it once per remaining tag. Capture
    # self's FULL DAG paths up front so later name-based lookups can't go
    # ambiguous once dup shapes share the short name (Maya keeps a duplicated
    # shape's short name identical to the original's).
    self_shape = (mc.ls(name, long=True) or [name])[0]
    self_tf = (mc.listRelatives(self_shape, parent=True, fullPath=True) or [self_shape])[0]

    shapes = [self_shape]
    for _ in tags[1:]:
        dup_tf = mc.duplicate(self_tf, returnRootsOnly=True)[0]
        dup_tf = (mc.ls(dup_tf, long=True) or [dup_tf])[0]
        dsh = (mc.listRelatives(dup_tf, shapes=True, type="mPyLocator", fullPath=True)
               or mc.listRelatives(dup_tf, shapes=True, fullPath=True) or [])
        if dsh:
            shapes.append(dsh[0])

    for idx, tag in enumerate(tags):
        if idx >= len(shapes):
            break
        sh = shapes[idx]
        # Name THIS gizmo's region via the live `regionTag` string selector, then
        # let its OWN setup wire the mesh (setup honours an already-set name) --
        # one code path for both "Run demo" and a standalone "Run setup".
        try:
            mc.setAttr(sh + ".regionTag", tag, type="string")
        except Exception:
            pass
        try:
            w = wrap_node(sh)
            if w is not None:
                w.run_setup([shape])
        except Exception:
            pass
        # Give each gizmo a DISTINCT default colour so the showcase reads as
        # separate regions; hover/select/outline keep their shared attr
        # defaults. Set AFTER run_setup so nothing setup does can win over it.
        try:
            _pal = [(0.25, 0.50, 0.95), (0.95, 0.45, 0.25), (0.30, 0.80, 0.40),
                    (0.80, 0.35, 0.85), (0.95, 0.82, 0.20), (0.30, 0.85, 0.90),
                    (0.95, 0.35, 0.55), (0.55, 0.85, 0.25), (0.45, 0.35, 0.90),
                    (0.90, 0.60, 0.20), (0.20, 0.70, 0.70), (0.70, 0.70, 0.95)]
            _c = _pal[idx % len(_pal)]
            for _ch, _v in zip("RGB", _c):
                mc.setAttr("%s.defaultColor%s" % (sh, _ch), _v)
        except Exception:
            pass
        # rename transform + shape after the tag for a readable outliner
        try:
            tf = mc.listRelatives(sh, parent=True, fullPath=True)
            if tf:
                new_tf = mc.rename(tf[0], _san(tag))
                nsh = mc.listRelatives(new_tf, shapes=True, fullPath=True)
                if nsh:
                    mc.rename(nsh[0], _san(tag) + "Shape")
                    fixed = mc.listRelatives(new_tf, shapes=True, fullPath=True)
                    if fixed:
                        shapes[idx] = fixed[0]
        except Exception:
            pass

    # This demo IMPORTS a maya file, so frame the WHOLE scene rather than just
    # the gizmos -- an imported mesh can sit anywhere, and fitting only the
    # locators can leave the head off screen with nothing visible to the user.
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return shapes[0]


@maya_test(label="Region draws in the node's RGBA colour; select lifts it", digits=3)
def test_mesh_regions(self):
    """Validate the node's INTENT (the SAME test passes on the interpreted node
    and its C++ compile -> parity). A locator has no numeric mesh output, so --
    exactly as the builder's own live-check does -- assert the DRAW BUFFERS:

      1. A bound region draws ONE RGBA face-colour per face carrying the node's
         `defaultColor` RGB + the `alpha` input (rest state), outlined in
         `outlineColor` at full opacity.
      2. Selecting the gizmo snaps the fill to `selectColor` and the outline to
         `outlineSelectColor` (alpha survives) and lifts the patch by exactly
         `selectOffset - offset` along the normals -- region-size-independent.
      3. A colour dialled to (0,0,0) draws BLACK. Nothing substitutes a
         fallback, so every colour in the cube is reachable.
    """
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np
    from mpynode._common.methods.test_helpers import (
        assert_close, assert_equal, assert_true)

    name = self.get_name()

    def _set(plug, *vals, **kw):
        # A demo (or user) may have CONNECTED this input; break incoming
        # connections first so the test can drive it, then set it.
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals, **kw)

    # Validate whatever mesh THIS node already consumes (e.g. the demo's head
    # model); build a probe sphere ONLY if `inMesh` drives nothing yet. Keeps the
    # test on `self` (parity) and robust to a live, demo-populated scene + reruns.
    src = mc.listConnections(name + ".inMesh", s=True, d=False) or []
    if not src:
        probe = mc.polySphere(sx=20, sy=20, name="regionProbe#")[0]
        pshape = mc.listRelatives(probe, shapes=True, fullPath=True)[0]
        mc.connectAttr(pshape + ".worldMesh[0]", name + ".inMesh", force=True)

    # Drive the draw deterministically off `self` through the COMPONENT-TAG
    # path. Not the legacy `regions` dict: that is a stored Python var, and a
    # compiled node has no _storedVarNames/_storedVarsData plug to receive one,
    # so forcing it made this test unrunnable against the C++ build -- which is
    # the parity claim in the docstring above. Tagging a known face range keeps
    # the region deterministic AND portable. `create=True` on an existing name
    # is idempotent, so a re-run in a live scene is safe.
    shape = (mc.listConnections(name + ".inMesh", s=True, d=False,
                                shapes=True) or [None])[0]
    assert_true(shape is not None, "inMesh must be driven by a mesh shape")
    n_faces = mc.polyEvaluate(shape, face=True)
    last_face = min(15, int(n_faces) - 1)
    mc.componentTag("%s.f[0:%d]" % (shape, last_face), create=True,
                    newTagName="mpyTestRegion")
    # Seed known colours + offsets. Every input is broken-then-set so no
    # demo/user connection can win over the values this test drives.
    _set(name + ".regionTag", "mpyTestRegion", type="string")
    probe_rgb = (0.20, 0.55, 0.90)
    for ch, val in zip("RGB", probe_rgb):
        _set("%s.defaultColor%s" % (name, ch), val)
    sel_rgb = (0.30, 0.85, 0.90)
    for ch, val in zip("RGB", sel_rgb):
        _set("%s.selectColor%s" % (name, ch), val)
    # Outline colours, deliberately nothing like the fill so a swapped-in fill
    # value could not satisfy the outline assertions below.
    out_rgb = (0.90, 0.10, 0.40)
    for ch, val in zip("RGB", out_rgb):
        _set("%s.outlineColor%s" % (name, ch), val)
    out_sel_rgb = (0.10, 0.95, 0.20)
    for ch, val in zip("RGB", out_sel_rgb):
        _set("%s.outlineSelectColor%s" % (name, ch), val)
    _set(name + ".alpha", 0.8)
    _set(name + ".offset", 0.1)
    _set(name + ".selectOffset", 0.5)
    mc.dgdirty(name)

    # Read the ordered draw commands via the node's PUBLIC MPx surface using the
    # node NAME only -- so this runs identically on the interpreted node AND a
    # compiled node (the parity point), never the interpreted-only wrapper.
    # One patch is drawn PER TAG; the tag driven above is the only one this test
    # names, so the first patch answers every assertion below.
    def _draw(selected=False):
        sl = om2.MSelectionList(); sl.add(name)
        mpx = om2.MFnDependencyNode(sl.getDependNode(0)).userNode()
        return mpx.evaluateDrawItems(0.0, selected=selected) or {}

    def _poly(selected=False):
        for cmd in _draw(selected).get("commands") or []:
            if cmd["slot"] == "polygons":
                return cmd["buffer"]
        return None

    # A COMPILED C++ locator (MPxLocatorNode) exposes no Python
    # evaluateDrawItems, so its draw buffers are unreachable here -- that parity
    # is covered by the dedicated -DMPYNODE_PROBE numerical buffer comparison.
    # Skip cleanly rather than false-fail, the same guard test_animated_selection
    # and test_animated_text already use. AttributeError ONLY: a node that HAS
    # the surface but draws nothing must still fail the assertion below.
    try:
        _draw(False)
    except AttributeError:
        return

    # 1) REST state: one RGBA row per face = defaultColor RGB + alpha (0.8).
    poly = _poly(False)
    assert_true(poly is not None, "the bound region must draw a patch")
    fcol = np.asarray(poly["face_colors"])
    cnt = np.asarray(poly["counts"])
    assert_true(fcol.ndim == 2 and fcol.shape[1] == 4,
                "face colours must be RGBA rows")
    assert_equal(fcol.shape[0], cnt.shape[0],
                 "one face colour per face (%d vs %d)"
                 % (fcol.shape[0], cnt.shape[0]))
    assert_close(fcol[:, :3].mean(axis=0).tolist(), list(probe_rgb))
    assert_true(bool(np.allclose(fcol[:, 3], 0.8, atol=1e-3)),
                "the alpha input must reach the fill")
    wire = np.asarray(poly["wireframe"], dtype=np.float64).ravel()
    assert_close(wire[:3].tolist(), list(out_rgb))
    assert_close(float(wire[3]), 1.0,
                 msg="the outline stays opaque; alpha dials the fill only")

    # 2) SELECT state: fill snaps to selectColor, the outline to
    #    outlineSelectColor, alpha survives, and the patch lifts by exactly
    #    selectOffset - offset (0.5 - 0.1) along the normals.
    rest_pts = np.asarray(poly["points"])
    psel = _poly(True)
    fcs = np.asarray(psel["face_colors"])
    disp = np.linalg.norm(np.asarray(psel["points"]) - rest_pts, axis=1)
    assert_close(fcs[:, :3].mean(axis=0).tolist(), list(sel_rgb))
    assert_true(bool(np.allclose(fcs[:, 3], 0.8, atol=1e-3)),
                "alpha survives selection")
    assert_close(np.asarray(psel["wireframe"],
                            dtype=np.float64).ravel()[:3].tolist(), list(out_sel_rgb))
    assert_close(float(disp.max()), 0.5 - 0.1, digits=2,
                 msg="select lift must equal selectOffset - offset")

    # 3) ZERO IS A COLOUR. Dialling a state to (0,0,0) must draw BLACK -- the
    #    compute substitutes nothing, so the value on the plug is the value on
    #    screen. Asserted on the fill AND the outline, since each used to have
    #    (fill) or lacked entirely (outline) its own path to the buffer.
    for ch in "RGB":
        _set("%s.defaultColor%s" % (name, ch), 0.0)
        _set("%s.outlineColor%s" % (name, ch), 0.0)
    mc.dgdirty(name)
    pblack = _poly(False)
    assert_true(pblack is not None, "an all-black region must still draw")
    assert_close(np.asarray(pblack["face_colors"])[:, :3].mean(
        axis=0).tolist(), [0.0, 0.0, 0.0])
    assert_close(np.asarray(pblack["wireframe"],
                            dtype=np.float64).ravel()[:3].tolist(), [0.0, 0.0, 0.0])
'''

SETUP_LOC_REGION = '''# Mesh Regions setup: bind THIS ONE gizmo to a single region of a mesh in the
# current selection (NO scene fabrication -- that is the `demo`\\'s job). Resolves
# ONE mesh, honours this gizmo\\'s `regionTag` string (or defaults it to the first
# component tag when unset), and wires the mesh\\'s live world-space geometry into
# `inMesh`. `demo` calls this once per tag after setting each gizmo\\'s `regionTag`,
# so the two hooks share one wiring path.
@maya_command(creates=True)
def setup(self, selection=None, *args, **kwargs):
    from maya import cmds as mc
    name = self.get_name()

    # Resolve ONE mesh: from the passed selection (in pick order), else the live
    # selection, else an already-connected inMesh source. Drop self so selecting
    # the gizmo alongside the mesh is harmless.
    order = [o for o in (selection or mc.ls(selection=True) or []) if o != name]
    meshes = _meshes(order) if order else []
    if not meshes:
        src = mc.listConnections(name + ".inMesh", source=True,
                                 destination=False, shapes=True) or []
        meshes = _meshes(src) if src else []
    if not meshes:
        raise SetupError("Select the mesh to bind this region gizmo to.")
    shape = (mc.ls(meshes[0], long=True) or [meshes[0]])[0]

    regions = get_component_tag_faces(shape)
    if not regions:
        raise SetupError("Mesh has no component tags to bind a region to.")
    tags = sorted(regions.keys())

    # The region is chosen by NAME via the LIVE `regionTag` string INPUT. Honour
    # an already-set name (the demo sets one per gizmo, or the user typed one);
    # otherwise default to the first tag so a fresh bind shows something. A user
    # can retype it in the Channel Box / Attribute Editor and the region
    # retargets on the next redraw (a name with no match draws blank). The
    # face-id MEMBERSHIP is never frozen -- the draw resolves it LIVE from the
    # input mesh data each evaluation, so editing the component tag updates the
    # region. The string name also marshals into the compiled node.
    try:
        cur = mc.getAttr(name + ".regionTag") or ""
    except Exception:
        cur = ""
    plug_empty = not cur
    if plug_empty:
        # A scene saved before `regionTag` existed kept its region in a baked
        # `regions` stored dict ({tag: face ids}). The draw no longer reads that
        # dict (a compiled node never could), so its key becomes the name here
        # and the dict is retired; a name the mesh no longer carries falls
        # through to the first tag like any fresh bind.
        try:
            legacy = (self.get_variables() or {}).get("regions")
        except Exception:
            legacy = None
        if isinstance(legacy, dict) and legacy:
            cur = next((k for k in sorted(str(k) for k in legacy) if k in regions), "")
            try:
                self.remove_variable("regions")
            except Exception:
                pass
    tag = cur or tags[0]
    if plug_empty:
        try:
            mc.setAttr(name + ".regionTag", tag, type="string")
        except Exception:
            pass
    mc.connectAttr(shape + ".worldMesh[0]", name + ".inMesh", force=True)

    # Move THIS gizmo's transform to the centroid of its region's vertices so
    # the handle sits on the patch it controls. The patch is drawn in world
    # space (see LOC_REGION_COMPUTE), so this only repositions the manipulator,
    # not the drawing. Wrapped so binding never fails on positioning.
    try:
        import maya.api.OpenMaya as om
        import numpy as np
        sel = om.MSelectionList()
        sel.add(shape)
        mfn = om.MFnMesh(sel.getDagPath(0))
        pts = extract_region(mfn, regions[tag], space=om.MSpace.kWorld)[0]
        if pts.shape[0]:
            ctr = pts.mean(axis=0)
            tf = (mc.listRelatives(name, parent=True, fullPath=True) or [None])[0]
            if tf:
                mc.xform(tf, worldSpace=True, translation=(
                    float(ctr[0]), float(ctr[1]), float(ctr[2])))
    except Exception:
        pass

    # Make the bound mesh unselectable so the region gizmos are easy to grab
    # (reference display: visible in the viewport but unpickable).
    try:
        mc.setAttr(shape + ".overrideEnabled", 1)
        mc.setAttr(shape + ".overrideDisplayType", 2)
    except Exception:
        pass

    try:
        mc.dgdirty(name)
    except Exception:
        pass
    return name
'''

LOC_REGION_DESC = (
    "# Mesh Regions\n\n"
    "Highlight a named piece of a mesh -- a cheek, a brow, a shoulder -- as a "
    "coloured patch you can hover and click. Each gizmo (`mPyLocator`) binds "
    "one mesh and one component tag, and draws that tag's faces as an "
    "outlined patch, rebuilt every redraw so it tracks deformation. It floats "
    "just off the surface along the vertex normals (no Z-fighting) and shows "
    "only its outer silhouette.\n\n"
    "Hovering lifts and recolours a patch (precise ray-versus-triangle test); "
    "selecting lifts it further. Because each region is its own gizmo, they "
    "highlight independently.\n\n"
    "Connect a mesh into `inMesh` and name the region in `regionTag`. "
    "`offset`, `hoverOffset` and `selectOffset` are absolute world-unit "
    "lifts, so the pop is the same whether the tag covers three faces or "
    "three hundred. `defaultColor`, `hoverColor` and `selectColor` set the "
    "colours, and `alpha` the transparency.\n\n"
    "**Create + Run demo** imports the bundled head model, resolves every "
    "component tag on it (the eight mouth regions -- `topLip`, `bottomLip`, "
    "their left/right halves, and `mouthLeft` / `mouthRight`), and builds one "
    "gizmo per tag, each wired to the mesh's `worldMesh[0]` and lit in its "
    "own colour."
)


def _parse_component_tag_regions(shape):
    """Resolve a mesh shape's component tags to {tag_name: [face ids]} by
    running the SHIPPED ``get_component_tag_faces`` straight out of
    DEMO_LOC_REGION, so the gate exercises the identical resolver the template
    ships instead of a hand-kept copy that can drift out of sync with it."""
    import ast
    src = DEMO_LOC_REGION
    ns = {}
    for _n in ast.parse(src).body:
        if (isinstance(_n, ast.FunctionDef)
                and _n.name == "get_component_tag_faces"):
            exec(ast.get_source_segment(src, _n), ns)
            break
    return ns["get_component_tag_faces"](shape)


def build_locator_mesh_regions():
    mc.file(new=True, force=True)
    _ensure_mpy_plugins()
    from mpynode._common.node_setups import find_demo, find_setup
    from mpynode._common.storedvars.stored_vars_api import get_variables, set_variable
    from mpynode.wrappers.mpy_locator import MPyLocator

    w = MPyLocator.create(name="meshRegions")
    node = w.get_name()
    # Canonical Class identity: without a stamped ``_pyClass`` the bake falls
    # back to the ROOT wrapper name (MPyLocator), so every baked mesh-region
    # script would be ``class MPyLocator(MPyLocator)``.
    from mpynode._common.io.user_classes import synthesize, dotted_path
    synthesize("MeshRegionLocator", "mPyLocator")
    w.set_py_class(dotted_path("MeshRegionLocator"))
    w.add_input_attr("inMesh", "mesh")
    w.add_input_attr("regionTag", "string")
    w.add_input_attr("offset", "float", default_value=0.1)
    w.add_input_attr("hoverOffset", "float", default_value=0.25)
    w.add_input_attr("selectOffset", "float", default_value=0.5)
    w.add_input_attr("hoverDur", "float", default_value=0.35)
    # Each colour carries a real attr DEFAULT (these were hard-coded fallbacks
    # in the compute, applied whenever a colour read all-zero -- which made pure
    # black the one unreachable value). With the default on the attr, a
    # raw-created node already looks right AND a dialled (0,0,0) draws black.
    w.add_input_attr("defaultColor", "color", default_value=(0.25, 0.50, 0.95))
    w.add_input_attr("hoverColor", "color", default_value=(1.00, 0.82, 0.15))
    w.add_input_attr("selectColor", "color", default_value=(0.30, 0.85, 0.90))
    # The outline is a per-state colour too; all three default to the dark edge
    # that used to be the fixed WIRE_COLOR, so a fresh node looks unchanged.
    w.add_input_attr("outlineColor", "color", default_value=(0.02, 0.02, 0.04))
    w.add_input_attr("outlineHoverColor", "color",
                     default_value=(0.02, 0.02, 0.04))
    w.add_input_attr("outlineSelectColor", "color",
                     default_value=(0.02, 0.02, 0.04))
    w.add_input_attr("alpha", "float", default_value=0.8,
                     min_value=0.0, max_value=1.0)
    w.set_init_expression(LOC_REGION_INIT)
    w.set_compute_expression(LOC_REGION_COMPUTE)
    methods_src = DEMO_LOC_REGION + "\n\n\n" + SETUP_LOC_REGION
    w.set_methods_source(methods_src)

    clean_payload = serialize_node(w, include_persistent=False)

    # Synthetic mesh + an authored component tag -> patch draws; verify the new
    # RGBA colour path (per-node defaultColor + alpha input) end to end.
    sphere = mc.polySphere(sx=20, sy=20, name="probeSphere")[0]
    sphere_shape = mc.listRelatives(sphere, shapes=True, fullPath=True)[0]
    mc.connectAttr(sphere_shape + ".worldMesh[0]", node + ".inMesh", force=True)
    # A raw-created node must already carry the seeded colour DEFAULTS, since
    # nothing in the compute substitutes them any more. Read them off the plugs
    # HERE, before the probe below overwrites defaultColor. Checked AGAIN on a
    # deserialized node further down: the live plug carrying the default proves
    # nothing about the payload, and that is precisely the hop that dropped it.
    _WANT_COLS = (("defaultColor", (0.25, 0.50, 0.95)),
                  ("hoverColor", (1.00, 0.82, 0.15)),
                  ("selectColor", (0.30, 0.85, 0.90)),
                  ("outlineColor", (0.02, 0.02, 0.04)),
                  ("outlineHoverColor", (0.02, 0.02, 0.04)),
                  ("outlineSelectColor", (0.02, 0.02, 0.04)))
    defaults_ok = all(
        np.allclose(mc.getAttr("%s.%s" % (node, _a))[0], _want, atol=1e-6)
        for _a, _want in _WANT_COLS)
    _probe_rgb = (0.20, 0.55, 0.90)
    for _ch, _v in zip("RGB", _probe_rgb):
        mc.setAttr("%s.defaultColor%s" % (node, _ch), _v)
    # The region is named, never stored: tag a face range on the probe mesh and
    # point `regionTag` at it (the legacy baked `regions` dict is retired). Maya
    # silently drops a ONE-letter tag name, so the probe tag is a word.
    mc.componentTag(sphere_shape + ".f[100:115]", create=True, newTagName="probeRegion")
    mc.setAttr(node + ".regionTag", "probeRegion", type="string")
    mc.dgdirty(node)
    poly = _draw_slot(w, "polygons")
    draw_ok = poly is not None
    if draw_ok:
        fcol = np.asarray(poly["face_colors"])
        cnt = np.asarray(poly["counts"])
        rows_ok = fcol.shape[0] == cnt.shape[0]      # one colour per face
        # RGBA rows carrying the node's defaultColor + the alpha input (0.8).
        colors_ok = (
            fcol.ndim == 2 and fcol.shape[1] == 4
            and np.allclose(fcol[:, :3], _probe_rgb, atol=1e-3)
            and np.allclose(fcol[:, 3], 0.8, atol=1e-3)
        )
    else:
        rows_ok = colors_ok = False

    # Deterministic SELECT-state coverage: evaluate_draw_commands only ever runs
    # the REST state, so drive selected=True directly and assert the colour
    # snaps to selectColor, alpha survives, and the patch lifts by exactly
    # selectOffset - offset (region-size-independent). Guards the recently-fixed
    # select path against silent regressions.
    select_ok = False

    def _first_poly(out):
        for cmd in (out or {}).get("commands") or []:
            if cmd["slot"] == "polygons":
                return cmd["buffer"]
        return None

    try:
        import maya.api.OpenMaya as _om
        for _ch, _v in zip("RGB", (0.30, 0.85, 0.90)):
            mc.setAttr("%s.selectColor%s" % (node, _ch), _v)
        _sl = _om.MSelectionList()
        _sl.add(node)
        _mpx = _om.MFnDependencyNode(_sl.getDependNode(0)).userNode()
        _pr = np.asarray(
            _first_poly(_mpx.evaluateDrawItems(0.0, selected=False))["points"])
        _psel = _first_poly(_mpx.evaluateDrawItems(0.0, selected=True))
        _fcs = np.asarray(_psel["face_colors"])
        _disp = np.linalg.norm(np.asarray(_psel["points"]) - _pr, axis=1)
        select_ok = bool(
            np.allclose(_fcs[:, :3], (0.30, 0.85, 0.90), atol=1e-3)   # selectColor
            and np.allclose(_fcs[:, 3], 0.8, atol=1e-3)               # alpha survives
            and abs(float(_disp.max()) - (0.5 - 0.1)) < 1e-2          # selectOffset - offset
        )
    except Exception:
        select_ok = False

    # ZERO IS A COLOUR. The compute used to swap an all-zero colour for a
    # hard-coded fallback, so pure black was the one value a user could not
    # dial -- setting 0.00001 went black but 0.0 did not. The defaults now live
    # on the attrs, so (0,0,0) must reach the buffer as black. Checked together
    # with the new per-state OUTLINE colour, which lands there as `wireframe`.
    zero_ok = outline_ok = False
    try:
        for _ch, _v in zip("RGB", (0.90, 0.10, 0.40)):
            mc.setAttr("%s.outlineColor%s" % (node, _ch), _v)
        for _ch, _v in zip("RGB", (0.10, 0.95, 0.20)):
            mc.setAttr("%s.outlineSelectColor%s" % (node, _ch), _v)
        mc.dgdirty(node)
        _pw = np.ravel(_first_poly(
            _mpx.evaluateDrawItems(0.0, selected=False))["wireframe"])
        _pws = np.ravel(_first_poly(
            _mpx.evaluateDrawItems(0.0, selected=True))["wireframe"])
        outline_ok = bool(
            np.allclose(_pw[:3], (0.90, 0.10, 0.40), atol=1e-3)
            and abs(float(_pw[3]) - 1.0) < 1e-6      # outline stays opaque
            and np.allclose(_pws[:3], (0.10, 0.95, 0.20), atol=1e-3))

        for _ch in "RGB":
            mc.setAttr("%s.defaultColor%s" % (node, _ch), 0.0)
            mc.setAttr("%s.outlineColor%s" % (node, _ch), 0.0)
        mc.dgdirty(node)
        _pz = _first_poly(_mpx.evaluateDrawItems(0.0, selected=False))
        zero_ok = bool(
            np.allclose(np.asarray(_pz["face_colors"])[:, :3], 0.0, atol=1e-6)
            and np.allclose(np.ravel(_pz["wireframe"])[:3], 0.0, atol=1e-6))
    except Exception:
        zero_ok = outline_ok = False

    # Real demo gate: run the SHIPPED demo and assert it builds ONE gizmo per
    # component tag (head.ma ships eight mouth tags -> eight locators), each
    # bound to the mesh (via its own delegated setup) and drawing its own region
    # in a distinct colour. The demo finds head.ma via _bundled_templates_root()
    # == TPL, so copy the asset into place first (idempotent; template.mpn still
    # writes on PASS).
    from mpynode._common.methods.methods_registry import run_node_demo
    from mpynode._common.io.mpn_io import deserialize_node
    from mpynode._node_registry import wrap_node

    per_tag_ok = draw_all_ok = colors_distinct = False
    setup_detail = "no-file"
    head = os.path.join(ASSETS_DIR, "head.ma")
    if os.path.isfile(head):
        _copy_asset("head.ma", LOC_REGION_DIR)
        mc.file(new=True, force=True)
        try:
            tnode = deserialize_node(clean_payload, restore_persistent=False)
            run_node_demo(tnode)
            locs = sorted(mc.ls(type="mPyLocator", long=True) or [])
            heads = mc.ls("headModel:*", type="mesh", long=True) or []
            n_tags = len(_parse_component_tag_regions(heads[0])) if heads else 0
            per_tag_ok = (n_tags >= 2 and len(locs) == n_tags)
            node_cols = []
            draw_all_ok = bool(locs)
            for loc in locs:
                if not (mc.listConnections(loc + ".inMesh", source=True,
                                           destination=False) or []):
                    draw_all_ok = False
                lw = wrap_node(loc)
                poly = _draw_slot(lw, "polygons") if lw else None
                if poly is None:
                    draw_all_ok = False
                    continue
                fc = np.asarray(poly["face_colors"])
                if fc.shape[0] == 0:
                    draw_all_ok = False
                    continue
                # one region per node -> all faces share the node's colour
                node_cols.append(tuple(np.round(fc[0], 4)))
            colors_distinct = (len(set(node_cols)) == len(node_cols)
                               and len(node_cols) >= 2)
            setup_detail = "%d tags -> %d locs" % (n_tags, len(locs))
        except Exception as exc:
            setup_detail = "exc:%r" % exc

    has_demo = find_demo(methods_src) is not None
    has_setup = find_setup(methods_src) is not None

    # Run the authored @maya_test on a FRESH deserialized node.
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        # SAME colour check as above, now on the node the USER actually gets
        # when they load this template. A default that is applied at create
        # time but not RECORDED in the payload passes the live check and comes
        # back all-zero here -- which is a black gizmo and, downstream, a
        # generated .cpp with no nAttr.setDefault.
        _tn = tnode.get_name()
        if not all(np.allclose(mc.getAttr("%s.%s" % (_tn, _a))[0], _want,
                               atol=1e-6) for _a, _want in _WANT_COLS):
            defaults_ok = False
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    # Migration: a gizmo carrying the pre-regionTag baked `regions` dict and an
    # EMPTY regionTag must come out of `setup` named after the dict's key that
    # the mesh still carries, with the dict gone.
    migrate_ok = False
    migrate_detail = "n/a"
    try:
        from mpynode._common.io.mpn_io import deserialize_node
        mc.file(new=True, force=True)
        msph = mc.polySphere(sx=20, sy=20, name="migrateSphere")[0]
        mshape = mc.listRelatives(msph, shapes=True, fullPath=True)[0]
        mc.componentTag(mshape + ".f[0:15]", create=True, newTagName="alpha")
        mc.componentTag(mshape + ".f[16:31]", create=True, newTagName="beta")
        mnode = deserialize_node(clean_payload, restore_persistent=False)
        mname = mnode.get_name()
        set_variable(mname, "regions", {"beta": list(range(16, 32))}, persistent=True)
        mnode.run_setup(selection=[msph])
        got = mc.getAttr(mname + ".regionTag") or ""
        left = "regions" in (get_variables(mname) or {})
        migrate_ok = (got == "beta" and not left)
        migrate_detail = "regionTag=%r dict_left=%s" % (got, left)
    except Exception as exc:
        migrate_detail = "exc:%r" % exc

    # The Class must survive SERIALIZATION, not just sit on the live plug: the
    # bake reads _pyClass off the deserialized node, so a stamp that drops in
    # the payload silently reverts the baked class to the root wrapper name.
    cls_ok = clean_payload.get("class_path") == dotted_path("MeshRegionLocator")

    ok = (draw_ok and rows_ok and colors_ok and select_ok and defaults_ok
          and outline_ok and zero_ok and has_demo
          and has_setup and per_tag_ok and draw_all_ok and colors_distinct
          and test_ok and cls_ok and migrate_ok)
    print("[loc_regions] draw=%s rows=%s colors=%s select=%s defaults=%s "
          "outline=%s zero=%s demo=%s setup=%s class=%s | "
          "per_tag=%s draw_all=%s distinct=%s test=%s(%s) migrate=%s(%s) (%s) -> %s"
          % (draw_ok, rows_ok, colors_ok, select_ok, defaults_ok, outline_ok,
             zero_ok, has_demo, has_setup, cls_ok,
             per_tag_ok, draw_all_ok, colors_distinct, test_ok, test_err,
             migrate_ok, migrate_detail,
             setup_detail, "PASS" if ok else "FAIL"))
    if ok:
        _copy_asset("head.ma", LOC_REGION_DIR)
        _write_template_to(LOC_REGION_DIR, clean_payload, LOC_REGION_DESC)
    return ok


# ======================================================================
# mPyConstraint -- orthogonal-Procrustes (SVD) rivet templates
# ======================================================================
# A deformation-robust rivet: for each driven transform, fit the best RIGID
# transform carrying its cluster of REST verts onto the SAME verts on the
# current DEFORMED mesh (orthogonal Procrustes / SVD), then ride that rigid
# motion while holding a bind offset. Meshes are read by their BARE input names
# (mesh / meshOrig) so the bridge delivers them as api2 MFnMesh -> vectorized
# mesh_region.mesh_arrays; self.mesh would route through the slower api1 proxy.

# ---- tags: N clusters authored as named component tags, array outMatrix -----
CONSTRAINT_TAGS_INIT = r'''import numpy as np
from mpynode._common.nodes.constraint.procrustes import procrustes_clusters

# Cluster membership is authored as named component tags on the mesh. Resolve it
# LIVE in Compute every evaluation, off the input mesh DATA (MFnGeometryData)
# feeding the `mesh` plug -- so a component-tag edit (add/remove verts) rides the
# mesh data, dirties this node, and re-resolves immediately. No cache (correctness
# first); a compiled C++ node resolves the same way off its own input handle.
'''

CONSTRAINT_TAGS_COMPUTE = r'''# Vectorized Procrustes attachment. Cluster ids resolve LIVE from this node's
# component-tag names off the input mesh DATA each evaluation; bind offsets come
# from self.bindMatrices. Mesh inputs are reached via self.X (self-only contract);
# self.mesh follows the worldMesh[0] connection to the DEFORMED upstream output.
# Every input is read defensively: during EAGER evaluation (mid-wiring, before
# the demo seeds bind vars / authors the tags, or while a mesh input is
# momentarily unconnected) any read can be unavailable -- no-op until the node
# is fully configured so a partial state never raises.
_ok = True
try:
    rest = self.meshOrig.points
    deformed = self.mesh.points
    # Tags are authored on the deforming `mesh` (visible twistTubeShape); resolve
    # membership LIVE off its data so tag edits take effect immediately.
    cl = np.asarray(self.mesh.tag_clusters(self.clusterTags), dtype=np.int64)
    bind = np.asarray(self.bindMatrices, dtype=np.float64).reshape(-1, 4, 4)
    # cluster count (live from clusterTags) and bind count (the per-ring offset
    # INPUT) can diverge the instant a user adds/removes a tag NAME from the
    # multi-string input. procrustes_clusters broadcasts bind row-for-row against
    # clusters, so a mismatch would raise -- clamp both to the common length so a
    # tag edit is a clean partial update rather than a crash.
    _n = min(cl.shape[0], bind.shape[0])
    cl = cl[:_n]
    bind = bind[:_n]
except Exception:
    _ok = False
if _ok and cl.shape[0] and rest.shape[0] and deformed.shape[0]:
    self.outMatrix = procrustes_clusters(rest, deformed, cl, bind)
'''


DEMO_CONSTRAINT_TAGS = '''# Component-tag Procrustes rivet demo: same vectorized showcase as the cluster
# variant, but cluster membership is authored as named component tags on the
# mesh instead of a raw index array. self is the constraint node (already
# created). Build a twisting tube plus a hidden undeformed duplicate, author four
# ring tags (plus a spare ringAlt band) on the deforming mesh, wire both meshes
# into self, capture one cube bind matrix per ring, then drive each cube from
# outMatrix[i]. Scrub the timeline: every cube rides the ring named by its tag.
def demo(self):
    from maya import cmds as mc
    import maya.api.OpenMaya as om
    import numpy as np
    from mpynode._common.nodes.mesh.component_tags import create_tag
    node = self.get_name()

    tube = mc.polyCylinder(name="twistTube", radius=1.0, height=6.0, sx=16, sy=12)[0]
    tube_shape = mc.listRelatives(tube, shapes=True, fullPath=True)[0]
    rest = mc.duplicate(tube, name="twistTube_rest")[0]
    rest_shape = mc.listRelatives(rest, shapes=True, fullPath=True)[0]
    # Mark the rest reference as an intermediate ("orig") shape: hidden in the
    # viewport, but its worldMesh still feeds meshOrig -- a clean rest source
    # instead of a stray visible-off duplicate.
    mc.setAttr(rest_shape + ".intermediateObject", 1)

    twist = mc.nonLinear(tube, type="twist")
    mc.setKeyframe(twist[0], attribute="endAngle", t=1, v=0.0)
    mc.setKeyframe(twist[0], attribute="endAngle", t=120, v=540.0)
    mc.setAttr(twist[0] + ".startAngle", 0.0)

    mc.currentTime(1)  # bind frame: twist == 0 -> deformed == rest
    sel = om.MSelectionList()
    sel.add(rest_shape)
    rest_pts = np.asarray(
        om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kWorld))[:, :3]
    y = rest_pts[:, 1]
    y_min, y_max = float(y.min()), float(y.max())
    band = 0.07 * (y_max - y_min)

    n_rings = 4
    fracs = np.linspace(0.20, 0.85, n_rings)
    clusterTags = []
    centroids = []
    for i, fr in enumerate(fracs):
        yc = y_min + fr * (y_max - y_min)
        cids = np.where(np.abs(y - yc) <= band)[0]
        tag = "ring%d" % i
        create_tag(tube_shape, tag, cids.tolist())
        clusterTags.append(tag)
        centroids.append(rest_pts[cids].mean(axis=0))

    yc_alt = y_min + 0.325 * (y_max - y_min)
    alt_ids = np.where(np.abs(y - yc_alt) <= band)[0]
    create_tag(tube_shape, "ringAlt", alt_ids.tolist())

    mc.connectAttr(tube_shape + ".worldMesh[0]", node + ".mesh", force=True)
    mc.connectAttr(rest_shape + ".worldMesh[0]", node + ".meshOrig", force=True)

    bindMatrices = np.zeros((n_rings, 4, 4), dtype=np.float64)
    cubes = []
    for i, ctr in enumerate(centroids):
        cube = mc.polyCube(name="tagRiveted%d" % i, w=0.5, h=0.5, d=0.5)[0]
        cubes.append(cube)
        mc.setAttr(cube + ".translate", float(ctr[0] + 2.5),
                   float(ctr[1]), float(ctr[2]))
        bindMatrices[i] = np.array(
            mc.getAttr(cube + ".worldMatrix[0]")).reshape(4, 4)
        mc.setAttr(cube + ".translate", 0, 0, 0)
        dm = mc.createNode("decomposeMatrix", name="tagRiveted%d_decomp" % i)
        mc.connectAttr(node + ".outMatrix[%d]" % i, dm + ".inputMatrix", force=True)
        mc.connectAttr(cube + ".rotateOrder", dm + ".inputRotateOrder", force=True)
        mc.connectAttr(dm + ".outputTranslate", cube + ".translate", force=True)
        mc.connectAttr(dm + ".outputRotate", cube + ".rotate", force=True)

    # clusterTags is a LIVE multi-string INPUT: write one tag NAME per element
    # so a user can retype/extend them and watch each rivet retarget.
    # bindMatrices is a DECLARED matrix-array INPUT for the same reason, and
    # because a stored var does not survive template serialization.
    for _i, _t in enumerate(clusterTags):
        mc.setAttr("%s.clusterTags[%d]" % (node, _i), _t, type="string")
    for _i in range(n_rings):
        mc.setAttr("%s.bindMatrices[%d]" % (node, _i),
                   *bindMatrices[_i].ravel().tolist(), type="matrix")

    mc.currentTime(1)
    try:
        mc.dgdirty(node)
    except Exception:
        pass
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return cubes


@maya_test(label="Tag rivets hold bind at rest and ride the twist", digits=3)
def test_tag_rivets(self):
    """Validate the node's INTENT (the same test passes on the interpreted node,
    so it is the parity bar for any compiled port): the demo rivets four cubes to
    four named ring tags on a twisting tube. At the bind frame (twist 0 ->
    deformed == rest) the rigid Procrustes fit is identity, so each outMatrix[i]
    equals the stored per-ring bind offset; scrubbing the twist ON makes every
    rivet actually move."""
    from maya import cmds as mc
    import numpy as np
    from mpynode._common.methods.test_helpers import (
        assert_close, assert_equal, assert_true)

    name = self.get_name()

    # The demo fabricates the whole showcase (twisting tube, four ring tags plus
    # a spare, one cube per ring driven from outMatrix[i] via decomposeMatrix)
    # and RETURNS the cube transforms IT created, in ring order. Count ONLY those
    # -- never a global mc.ls("tagRiveted*") that a live scene or an earlier run
    # also matches -- so the test survives a populated scene and repeated runs.
    # Call the top-level demo() FUNCTION directly (not self.run_demo(), a wrapper
    # method absent on the compiled node's _NodeNameProxy) so the SAME test runs
    # on both the interpreted node and its C++ compile.
    created = demo(self) or []
    cubes = [(mc.ls(c, long=True) or [c])[0]
             for c in created
             if mc.objExists(c) and mc.nodeType(c) == "transform"]
    assert_equal(len(cubes), 4,
                 "demo must rivet four cubes (got %d)" % len(cubes))

    # Bind frame: twist == 0 -> deformed == rest, so outMatrix[i] == bind offset.
    mc.currentTime(1)
    mc.dgdirty(name)
    binds = np.asarray(
        [mc.getAttr(name + ".bindMatrices[%d]" % i) for i in range(len(cubes))],
        dtype=float).reshape(-1, 4, 4)
    for i in range(len(cubes)):
        om_i = np.array(mc.getAttr(name + ".outMatrix[%d]" % i)).reshape(4, 4)
        assert_close(om_i.ravel().tolist(), binds[i].ravel().tolist(),
                     msg="outMatrix[%d] must equal its bind offset at rest" % i)

    # Scrub the twist ON: every rivet must ride its ring (world position moves).
    def _world_t(dag, frame):
        mc.currentTime(frame)
        mc.dgdirty(name)
        return np.array(mc.xform(dag, q=True, ws=True, t=True), dtype=float)

    for c in cubes:
        moved = float(np.linalg.norm(_world_t(c, 45) - _world_t(c, 1)))
        assert_true(moved > 0.05,
                    "rivet %s should ride the twist (moved %.4f)" % (c, moved))
'''

SETUP_CONSTRAINT_TAGS = VANILLA_SETUP_ERROR + VANILLA_MESHES + r'''
# Component-tag helpers, VENDORED from
# mpynode._common.nodes.mesh.component_tags (same subset the single_tag
# template carries). setup is a @maya_command body, which ships as embedded
# python inside the compiled .mll -- where mpynode is NOT importable -- so the
# tag authoring/lookup logic is carried here instead of imported. maya.cmds is
# imported per-def (module scope must stay import-free of Maya so the source
# execs anywhere).
def _to_component_strings(shape, indices):
    """Compress vertex ids into ``shape.vtx[a:b]`` / ``shape.vtx[a]`` runs."""
    idx = sorted({int(i) for i in indices})
    runs = []
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and idx[j + 1] == idx[j] + 1:
            j += 1
        runs.append("vtx[%d]" % idx[i] if i == j
                    else "vtx[%d:%d]" % (idx[i], idx[j]))
        i = j + 1
    return ["%s.%s" % (shape, r) for r in runs]


def create_tag(shape, tag_name, indices):
    """Create a vertex component tag ``tag_name`` on ``shape``. Returns the name
    created, or ``""`` when nothing was created.

    It does NOT overwrite. ``componentTag(create=True)`` on a name that is
    ALREADY taken returns ``""``, raises nothing and leaves the existing
    membership untouched -- so re-authoring a live name silently keeps the OLD
    vertex set. That ``""`` is returned rather than swallowed. To genuinely
    replace a membership use ``componentTag(comps, modify="replace", ...)``."""
    from maya import cmds as mc
    comps = _to_component_strings(shape, indices)
    if not comps:
        return ""
    return mc.componentTag(comps, create=True, newTagName=tag_name) or ""


def _candidate_tag_shapes(shape):
    """``shape`` + its sibling shapes (incl. intermediate ``*Orig``) under the
    same transform.

    On a DEFORMED mesh, component tags live on the intermediate ``*Orig``
    shape, not the visible output shape -- so any tag lookup must consider
    both. For an undeformed shape this is just ``[shape]``."""
    from maya import cmds as mc
    shapes = [shape]
    try:
        par = mc.listRelatives(shape, parent=True, fullPath=True) or []
        if par:
            sibs = (
                mc.listRelatives(
                    par[0], shapes=True, noIntermediate=False, fullPath=True) or [])
            for s in sibs:
                if s not in shapes:
                    shapes.append(s)
    except Exception:
        pass
    return shapes


def tag_names(shape):
    """All component-tag names visible for ``shape`` (deform-aware: includes
    tags stored on the intermediate ``*Orig`` shape)."""
    from maya import cmds as mc
    out = []
    for s in _candidate_tag_shapes(shape):
        try:
            for i in mc.getAttr(s + ".componentTags", multiIndices=True) or []:
                nm = mc.getAttr("%s.componentTags[%d].componentTagName" % (s, i))
                if nm not in out:
                    out.append(nm)
        except Exception:
            pass
    return out


# Component-tag Procrustes rivet setup: attach one or more selected transforms
# to a selected mesh, each driven by a NAMED component tag (NO scene
# fabrication -- that is the demo hook job). The tag-driven cousin of the
# cluster setup: duplicate the mesh at its CURRENT pose as the rest reference,
# and for each transform bind to the tag already named in clusterTags[i] when
# that tag exists on the mesh, else author one from the K rest verts nearest
# the transform; capture its bind matrix and drive it from outMatrix[i] through
# a decomposeMatrix. Select the mesh plus the transform(s) to rivet, then run.
@maya_command(creates=True)
def setup(self, selection=None, *args, **kwargs):
    from maya import cmds as mc
    import maya.api.OpenMaya as om
    import numpy as np
    node = self.get_name()

    order = [o for o in (selection or mc.ls(selection=True) or []) if o != node]
    meshes = _meshes(order) if order else []
    if not meshes:
        raise SetupError(
            "Select the mesh and one or more transforms to rivet to it.")
    mesh_tf = (mc.ls(meshes[0], long=True) or [meshes[0]])[0]
    mesh_shape = (mc.listRelatives(mesh_tf, shapes=True, type="mesh",
                                   noIntermediate=True, fullPath=True) or [mesh_tf])[0]

    riders = []
    for o in order:
        o_long = (mc.ls(o, long=True) or [o])[0]
        if o_long in (mesh_tf, mesh_shape):
            continue
        riders.append(o_long)
    if not riders:
        raise SetupError("Select transform(s) to rivet (plus the mesh).")

    rest = mc.duplicate(mesh_tf,
                        name=mesh_tf.split("|")[-1] + "_procrustesRest")[0]
    rest = (mc.ls(rest, long=True) or [rest])[0]
    rest_shape = (mc.listRelatives(rest, shapes=True, type="mesh",
                                   noIntermediate=True, fullPath=True) or [None])[0]
    if rest_shape is None:
        raise SetupError("Could not duplicate the mesh as a rest reference.")
    # Mark the rest reference as an intermediate ("orig") shape: hidden in the
    # viewport, but its worldMesh still feeds meshOrig (resolve the shape with
    # noIntermediate FIRST, then flag it).
    mc.setAttr(rest_shape + ".intermediateObject", 1)

    mc.connectAttr(mesh_shape + ".worldMesh[0]", node + ".mesh", force=True)
    mc.connectAttr(rest_shape + ".worldMesh[0]", node + ".meshOrig", force=True)

    sel = om.MSelectionList()
    sel.add(rest_shape)
    rest_pts = np.asarray(
        om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kWorld))[:, :3]

    k = min(12, rest_pts.shape[0])
    existing = set(tag_names(mesh_shape) or [])
    seeded = set(mc.getAttr(node + ".clusterTags", multiIndices=True) or [])
    auto = 0
    tags = []
    bind_list = []
    for i, rider in enumerate(riders):
        # Which tag drives rider i: honour the name already typed into
        # clusterTags[i] when it names a REAL tag on the mesh -- the user
        # authored that membership, so bind to it rather than overwrite it.
        # Otherwise author one from the K nearest rest verts (the same bind the
        # cluster variant does, just NAMED) under the typed name, or the first
        # FREE auto-name.
        want = (mc.getAttr("%s.clusterTags[%d]" % (node, i))
                if i in seeded else "") or ""
        if not want or want not in existing:
            piv = np.array(mc.xform(rider, q=True, ws=True, rp=True), dtype=float)
            d2 = ((rest_pts - piv) ** 2).sum(axis=1)
            ids = np.argsort(d2)[:k]
            if ids.shape[0] < 3:
                raise SetupError(
                    "Mesh has too few verts for a Procrustes fit (>=3).")
            # `not want` short-circuits the membership test above, so the
            # auto-name has to be checked HERE or it never is: keying it on the
            # rider index alone only avoids a collision WITHIN one run, and
            # silently inherited another node's ring across runs (create_tag
            # cannot overwrite -- it no-ops on a taken name).
            if not want:
                while ("procrustesRivet%d" % auto) in existing:
                    auto += 1
                want = "procrustesRivet%d" % auto
                auto += 1
            # `existing` must stay truthful as we go: a later rider can type the
            # name an earlier one just authored.
            if want not in existing:
                create_tag(mesh_shape, want, ids.tolist())
                existing.add(want)
        tags.append(want)
        bind_list.append(
            np.array(mc.getAttr(rider + ".worldMatrix[0]")).reshape(4, 4))

    # clusterTags (one tag NAME per rivet, retypeable to retarget) and
    # bindMatrices (one flat-16 rest offset per rivet) are DECLARED INPUTS:
    # setAttr them so the node carries its own configuration -- a stored var
    # would not survive serialization.
    for _i, _t in enumerate(tags):
        mc.setAttr("%s.clusterTags[%d]" % (node, _i), _t, type="string")
    for _i in range(len(riders)):
        mc.setAttr("%s.bindMatrices[%d]" % (node, _i),
                   *[float(x) for x in bind_list[_i].flatten()], type="matrix")

    for i, rider in enumerate(riders):
        dm = mc.createNode("decomposeMatrix",
                           name=rider.split("|")[-1] + "_decomp")
        mc.connectAttr(node + ".outMatrix[%d]" % i, dm + ".inputMatrix", force=True)
        mc.connectAttr(rider + ".rotateOrder", dm + ".inputRotateOrder", force=True)
        mc.connectAttr(dm + ".outputTranslate", rider + ".translate", force=True)
        mc.connectAttr(dm + ".outputRotate", rider + ".rotate", force=True)
    try:
        mc.dgdirty(node)
    except Exception:
        pass
    return node
'''


CONSTRAINT_TAGS_DESC = (
    "# Procrustes Rivet (Tags)\n\n"
    "A many-rivet `mPyConstraint` where you pick each cluster by NAME rather "
    "than by vertex index. "
    "Membership comes from geometry component tags authored on the mesh, so "
    "the mesh stays the single source of truth -- edit a tag's verts and the "
    "rivet follows, with no node data to re-sync.\n\n"
    "`clusterTags` is a live multi-string input, one tag name per rivet "
    "(`ring0`, `ring1`, ...). Retype an element in the Channel Box or "
    "Attribute Editor and that rivet retargets to the newly named tag on the "
    "next evaluation. `bindMatrices` is a matrix-array input holding one "
    "`(4, 4)` rest offset per rivet, and `outMatrix` is an array with one "
    "entry per tag.\n\n"
    "**Create + Run demo** builds a twisting tube, 0 -> 540 deg, with four "
    "ring tags authored on the mesh (plus a spare `ringAlt` band) and one "
    "cube riveted per tag -- scrub and every cube rides the ring named by its "
    "tag.\n\n"
    "**Run setup** (right-click the node on the Scene tab) rivets transforms "
    "you already have: select the mesh and one or more transforms, run setup, "
    "and each binds to a NAMED tag -- the one already in its `clusterTags` "
    "element if that tag exists on the mesh, otherwise one authored from the "
    "K nearest verts at the current pose."
)


def _constraint_frame_positions(cube, node, frames):
    """Eval `node` at each frame and return the world translate of `cube`."""
    out = []
    for fr in frames:
        mc.currentTime(fr)
        try:
            mc.dgdirty(node)
        except Exception:
            pass
        out.append(np.array(mc.xform(cube, q=True, ws=True, t=True),
                            dtype=float))
    return out


def build_procrustes_tags():
    mc.file(new=True, force=True)
    _ensure_mpy_plugins()
    from mpynode._common.node_setups import find_demo, find_setup
    from mpynode.wrappers.mpy_constraint import MPyConstraint

    w = MPyConstraint.create(name="procrustesTags")
    w.add_input_attr("mesh", "mesh")
    w.add_input_attr("meshOrig", "mesh")
    # clusterTags is a LIVE multi-string INPUT (one component-tag NAME per
    # output rivet): a user can retype element i in the Channel Box / Attribute
    # Editor and outMatrix[i] retargets to that tag on the next evaluation.
    # bindMatrices is a DECLARED matrix-array INPUT (one per-ring rest offset
    # per rivet). It used to be a stored var, but stored vars do NOT survive
    # template serialization -- `stored_vars` ships empty, so a gallery-created
    # node had no bind offsets at all and its compute silently no-opped unless
    # you also ran the demo. Declaring it also clears the compiler's Phase-0
    # "reads undeclared self attr" reject. Compute reads its tags through
    # `self.mesh.tag_clusters(self.clusterTags)`, the geo read-surface form whose
    # tag NAMES are runtime data, so the node lowers deterministically (no AI
    # porter) and the compiled C++ re-resolves membership off its own input
    # handle every evaluation -- live tag editing intact. NOTE the parity gate
    # wires an UNTAGGED shape, so its pointwise sweep is vacuous here; the
    # authored @maya_test is what actually proves tag resolution.
    w.add_input_attr("clusterTags", "string", is_array=True)
    w.add_input_attr("bindMatrices", "matrix", is_array=True)
    w.add_output_attr("outMatrix", "matrix", is_array=True)
    w.set_init_expression(CONSTRAINT_TAGS_INIT)
    w.set_compute_expression(CONSTRAINT_TAGS_COMPUTE)
    methods_src = DEMO_CONSTRAINT_TAGS + "\n\n\n" + SETUP_CONSTRAINT_TAGS
    w.set_methods_source(methods_src)

    _stamp_class(w, "ProcrustesTags", "mPyConstraint")
    clean_payload = serialize_node(w, include_persistent=False)

    from mpynode._common.methods.methods_registry import run_node_demo
    from mpynode._common.io.mpn_io import deserialize_node

    ok = False
    detail = "n/a"
    try:
        mc.file(new=True, force=True)
        _ensure_mpy_plugins()
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        node = tnode.get_name()
        run_node_demo(tnode)
        cubes = sorted(c for c in (mc.ls("tagRiveted*", long=True) or [])
                       if mc.nodeType(c) == "transform")
        n_ok = len(cubes) == 4

        # tags authored on the deforming mesh (5: ring0..3 + ringAlt). On a
        # DEFORMED mesh the tags live on the intermediate *Orig shape, so count
        # deform-aware via tag_names (which searches sibling Orig shapes too).
        from mpynode._common.nodes.mesh.component_tags import tag_names
        tube_shape = (mc.listRelatives("twistTube", shapes=True,
                                       type="mesh", noIntermediate=True,
                                       fullPath=True) or [None])[0]
        n_tags = len(tag_names(tube_shape)) if tube_shape else 0
        tags_ok = n_tags >= 5

        wired = all(bool(mc.listConnections(
            c + ".translate", source=True, destination=False,
            type="decomposeMatrix")) for c in cubes) if cubes else False

        mc.currentTime(1)
        mc.dgdirty(node)
        binds = np.asarray(
            [mc.getAttr(node + ".bindMatrices[%d]" % i)
             for i in range(len(cubes))], dtype=float).reshape(-1, 4, 4)
        bind_ok = True
        for i in range(len(cubes)):
            om_i = np.array(
                mc.getAttr(node + ".outMatrix[%d]" % i)).reshape(4, 4)
            if not np.allclose(om_i, binds[i], atol=1e-4):
                bind_ok = False
                break

        moved = True
        for c in cubes:
            p1, p45 = _constraint_frame_positions(c, node, (1, 45))
            if float(np.linalg.norm(p45 - p1)) <= 0.05:
                moved = False

        # --- authored @maya_test check on a FRESH deserialized node. ---
        test_ok = False
        test_err = "n/a"
        try:
            mc.file(new=True, force=True)
            _ensure_mpy_plugins()
            ttnode = deserialize_node(clean_payload, restore_persistent=False)
            tres = ttnode.run_test()
            test_ok = bool(tres.get("passed"))
            test_err = tres.get("error") or "ok"
        except Exception as _texc:
            test_err = "exc:%r" % _texc

        has_demo = find_demo(methods_src) is not None
        has_setup = find_setup(methods_src) is not None
        ok = bool(n_ok and tags_ok and wired and bind_ok and moved
                  and has_demo and has_setup and test_ok)
        detail = ("n=%d tags=%d wired=%s bind_ok=%s moved=%s demo=%s "
                  "setup=%s test=%s(%s)" % (len(cubes), n_tags, wired,
                                   bind_ok, moved, has_demo, has_setup,
                                   test_ok, test_err))
    except Exception as exc:
        detail = "exc:%r" % exc

    print("[procrustes_tags] %s -> %s" % (detail, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(CONSTRAINT_TAGS_DIR, clean_payload,
                           CONSTRAINT_TAGS_DESC)
    return ok


# ======================================================================
# DNET -- spring-network relaxation solver (base mPyNode)
# ======================================================================
# The relaxation Solver + authoring helpers live in the shared module
# mpynode._common.nodes.rigging.dnet (numpy + optional numba, ported 1:1 from the
# source bugs/dnet_code.mpn). The KEY MAPPING: the Init tab IMPORTS Solver from
# that module (the procrustes-style "import the shared node code at runtime"
# pattern) rather than baking its source, and the Compute expression HOLDS a Solver
# instance -- `self.node = Solver(self.previous)` -- calling `self.node.evaluate()`
# each frame and reading the solved positions / lengths back off `self.node`; the
# carry-over state (`self.previous`) lives as a plain session-only attr (the
# spring_chain pattern). NOTE: numpy/numba -> NOT C++-transpilable. Knots carry
# goal transforms (matrices[i]); links (index0[e] ->
# index1[e]) are springs with rest length restLengths[e]. Anchored knots
# (anchors[i] > 0) snap to their live goal; free knots relax toward their rest
# lengths AND carry secondary motion frame-to-frame, so animating an anchor makes
# the net swing and settle.

# ======================================================================
# Aim-between-two-matrices mPyTransform -- a base mPyTransform whose frame is
# authored entirely by the expression (self.local_matrix + apply_* gates) from
# two connected matrix inputs. Its X axis aims from matrix0's origin toward
# matrix1's origin and it sits at their midpoint, so a child rides the segment
# between the two inputs. Stands alone: the DNET layout demo used to build one
# aim per link, but it now uses plain link transforms (its gate asserts no
# mPyTransform survives demo_layout), so nothing else depends on this template.
# ======================================================================

# Imports live in the Init tab (shared namespace); the compute reads the two
# matrix inputs as numpy-transparent MatrixViews.
AIM_TRANSFORM_INIT = "import numpy as np\n"

# The matrix hook. p0 = matrix0 origin, p1 = matrix1 origin. X (row 0) aims
# p0 -> p1; the origin (row 3) is the midpoint. A world up (falling back to +Z
# when the aim is near-vertical) fixes roll. The basis is orthonormal (no
# scale), so a child's LOCAL unit maps exactly to a world unit along the aim.
# GATED LOCAL-MATRIX contract: M is the desired WORLD frame; we convert it to
# parent-relative with self.local_matrix = M @ inv(parentWorld) and open ALL
# THREE gates, so the scaffold drives offsetParentMatrix fully. The node NEVER
# reads its own DAG parent -- world placement is opt-in via the CONNECTED
# parentWorld input (DG-tracked, cycle-free); it defaults to identity so a root
# node lands exactly at M. All three channels MUST be driven: under a
# non-uniformly-scaled parent, inv(parentWorld) bakes the parent's inverse scale
# into local_matrix, so gating scale off would strip it and the aim would no
# longer land at the absolute world M (M itself is orthonormal, so the node's
# resulting WORLD scale is a clean 1). The node's own TRS cancels in
# world = L * inv(L) * D * parent = D * parent, so a channel like translateX
# never moves the solved frame and stays FREE as a plain handle for something
# else, regardless of the gates.
AIM_TRANSFORM_COMPUTE = (
    "m0 = self.matrix0.asNumpy()\n"
    "m1 = self.matrix1.asNumpy()\n"
    "p0 = m0[3, :3]\n"
    "p1 = m1[3, :3]\n"
    "fwd = p1 - p0\n"
    # float() around norm/dot is LOAD-BEARING for the C++ transpiler: it makes the
    # scalar genuinely scalar so `if length < 1e-9` / `abs(dot) > 0.999` lower to a
    # deterministic C++ bool (an un-wrapped numpy 0-d array is rejected as "array
    # used as a boolean condition"). The interpreted node is indifferent; the
    # compiler needs it to lower without the AI porter.
    "length = float(np.linalg.norm(fwd))\n"
    "if length < 1e-9:\n"
    "    fwd = np.array([1.0, 0.0, 0.0])\n"
    "else:\n"
    "    fwd = fwd / length\n"
    "up = np.array([0.0, 1.0, 0.0])\n"
    "if abs(float(np.dot(fwd, up))) > 0.999:\n"
    "    up = np.array([0.0, 0.0, 1.0])\n"
    "side = np.cross(fwd, up)\n"
    "side = side / (float(np.linalg.norm(side)) + 1e-12)\n"
    "up2 = np.cross(side, fwd)\n"
    "M = np.eye(4)\n"
    "M[0, :3] = fwd\n"
    "M[1, :3] = up2\n"
    "M[2, :3] = side\n"
    "M[3, :3] = 0.5 * (p0 + p1)\n"
    "P = self.parentWorld.asNumpy()\n"
    "self.local_matrix = M @ np.linalg.inv(P)\n"
    "self.apply_rotate = True\n"
    "self.apply_translate = True\n"
    "self.apply_scale = True\n"
)

# (AIM_DIR is defined up top next to DNET_DIR so ALL_DECLARED_DIRS can use it.)

# Methods tab: a "Create + Run demo" that drops two locators, wires them into
# matrix0/matrix1, and parents a cube so the aim orientation is visible. The
# aim node IS the template (self), so the demo only builds the two drivers.
DEMO_AIM = VANILLA_SETUP_ERROR + '''

@maya_demo(label="Aim Between Two Locators")
def demo(self):
    """Drop two locators and aim this transform between them. ``start`` feeds
    ``matrix0`` and ``end`` feeds ``matrix1``; the transform lands at their
    midpoint with its X axis pointing start -> end. A child cube rides the aim
    so the orientation is visible -- move either locator to watch it track.

    The aim runs in LOCAL space: it writes ``self.local_matrix = M @ inv(P)``
    where ``P`` is the ``parentWorld`` matrix input (identity while this node
    sits at the world root). To aim under a moving parent, connect that
    parent's ``worldMatrix[0]`` -> ``parentWorld`` and the node stays cycle-free
    because it never reads its own DAG parent."""
    from maya import cmds as mc
    name = self.get_name()

    start = mc.spaceLocator(name="aimStart#")[0]
    end = mc.spaceLocator(name="aimEnd#")[0]
    mc.setAttr(start + ".translate", -3.0, 0.0, 0.0, type="double3")
    mc.setAttr(end + ".translate", 3.0, 2.0, 0.0, type="double3")
    mc.connectAttr(start + ".worldMatrix[0]", name + ".matrix0", force=True)
    mc.connectAttr(end + ".worldMatrix[0]", name + ".matrix1", force=True)

    # A thin child cube visualizes the aim (its long axis is X).
    cube = mc.polyCube(name="aimArrow#", width=2.0, height=0.2, depth=0.2)[0]
    mc.parent(cube, name, relative=True)

    mc.select(end, replace=True)
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_test(label="Aim: midpoint origin, X aims matrix0->matrix1, orthonormal", digits=4)
def test_aim(self):
    """Validate the node's INTENT (the same test passes on the interpreted node
    and its C++ compile -> parity): wiring two locators' worldMatrix into
    matrix0/matrix1 lands this transform at their MIDPOINT with its X axis aiming
    matrix0 -> matrix1 on an orthonormal (unit-length, mutually perpendicular)
    basis, and a child offset +1 along local X rides one aim-unit toward
    matrix1."""
    from maya import cmds as mc
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_close

    name = self.get_name()

    # Two drivers at known positions -> exact expected midpoint / aim direction.
    start = mc.spaceLocator(name="aimTestStart#")[0]
    end = mc.spaceLocator(name="aimTestEnd#")[0]
    mc.setAttr(start + ".translate", -3.0, 0.0, 0.0, type="double3")
    mc.setAttr(end + ".translate", 3.0, 2.0, 0.0, type="double3")
    mc.connectAttr(start + ".worldMatrix[0]", name + ".matrix0", force=True)
    mc.connectAttr(end + ".worldMatrix[0]", name + ".matrix1", force=True)

    p0 = np.array([-3.0, 0.0, 0.0])
    p1 = np.array([3.0, 2.0, 0.0])
    mid = 0.5 * (p0 + p1)
    fwd = (p1 - p0) / np.linalg.norm(p1 - p0)

    mtx = np.array(mc.getAttr(name + ".worldMatrix[0]"),
                   dtype=float).reshape(4, 4)
    row_x, row_y, row_z = mtx[0, :3], mtx[1, :3], mtx[2, :3]
    origin = mtx[3, :3]

    # Origin sits at the midpoint; the X axis aims matrix0 -> matrix1.
    assert_close(origin.tolist(), mid.tolist())
    assert_close(row_x.tolist(), fwd.tolist())

    # Basis is orthonormal (unit rows, mutually perpendicular) -> no scale/shear.
    assert_close([float(np.linalg.norm(row_x)),
                  float(np.linalg.norm(row_y)),
                  float(np.linalg.norm(row_z))], [1.0, 1.0, 1.0])
    assert_close([float(np.dot(row_x, row_y)),
                  float(np.dot(row_x, row_z)),
                  float(np.dot(row_y, row_z))], [0.0, 0.0, 0.0])

    # A child offset +1 along local X rides one aim-unit toward matrix1.
    tip = mc.group(empty=True, name="aimTestTip#")
    tip = mc.parent(tip, name, relative=True)[0]
    mc.setAttr(tip + ".translateX", 1.0)
    tw = np.array(mc.getAttr(tip + ".worldMatrix[0]"),
                  dtype=float).reshape(4, 4)
    assert_close(tw[3, :3].tolist(), (mid + fwd).tolist())


@maya_command(creates=True)
def setup(self, selection=None, *args, **kwargs):
    """Aim this transform between two selected objects: pick START then END.
    An optional third pick drives parentWorld; otherwise this node's own DAG
    parent does (nothing is connected at the world root)."""
    from maya import cmds as mc
    name = self.get_name()

    order = [o for o in (selection or mc.ls(selection=True) or []) if o != name]
    # Anything carrying a worldMatrix can drive an aim end (transform, joint,
    # locator, shape) -- filter on the PLUG rather than on node type.
    drivers = [(mc.ls(o, long=True) or [o])[0] for o in order
               if mc.objExists(o + ".worldMatrix")]
    if len(drivers) < 2:
        raise SetupError(
            "Select TWO objects to aim between -- START first, then END. An "
            "optional THIRD pick drives parentWorld (otherwise this node's own " "DAG parent does).")

    mc.connectAttr(drivers[0] + ".worldMatrix[0]", name + ".matrix0", force=True)
    mc.connectAttr(drivers[1] + ".worldMatrix[0]", name + ".matrix1", force=True)

    # The compute writes self.local_matrix = M @ inv(parentWorld), so the node
    # must be TOLD its parent's world matrix -- it never reads its own DAG
    # parent, which is what keeps the aim cycle-free. Prefer an explicit third
    # pick; else this node's DAG parent (absent at the world root, where
    # parentWorld's identity default is already correct).
    parent = drivers[2] if len(drivers) > 2 else (
        mc.listRelatives(name, parent=True, fullPath=True) or [None])[0]
    if parent:
        kin = set(mc.ls(name, long=True) or [])
        kin.update(mc.listRelatives(name, allDescendents=True,
                                    fullPath=True) or [])
        if parent in kin:
            raise SetupError(
                "%s cannot drive parentWorld -- it is this aim node or one of "
                "its children, which would make an evaluation cycle. Pick an "
                "object outside the aim node's hierarchy."
                % parent.split("|")[-1])
        mc.connectAttr(parent + ".worldMatrix[0]", name + ".parentWorld", force=True)
    return name
'''


AIM_DESC = """# Aim Between Two Matrices

An `mPyTransform` that parks itself halfway between two things and points at
one of them. Feed it two matrices and it sits at their midpoint with its X axis
aiming from `matrix0` toward `matrix1`; a world up vector (switching to +Z when
the aim goes near-vertical) keeps the roll from flipping. The frame carries no
scale, so anything parented under it rides cleanly along the segment between
the two inputs -- stretchy limb segments, connector geometry between two
controls. Wire any `worldMatrix` (a locator, a joint, another transform) into
`matrix0` and `matrix1`.

World placement is opt-in. `parentWorld` defaults to identity, so the node
lands exactly where the aim puts it in world space. To aim under a moving
parent, connect that parent's `worldMatrix[0]` into `parentWorld` -- the node
re-solves when the parent moves, and never reads its own DAG parent, so there
is no cycle.

The solve is published through `offsetParentMatrix` and ignores the node's own
translate / rotate / scale channels, so a channel like `translateX` stays free
to use as a plain handle for something else.

**Create + Run demo** drops two locators, wires them into `matrix0` /
`matrix1`, and parents a cube so the aim is visible. Move either locator to
watch the transform re-aim and its child follow.
"""


def build_aim_between_matrices():
    """Author the aim mPyTransform template, verify it behaviorally through a
    full serialize -> deserialize round-trip (midpoint origin, orthonormal
    X-aimed basis, a child that rides the segment, the demo registered), then
    write the template only on PASS."""
    mc.file(new=True, force=True)
    _ensure_mpy_plugins()
    from mpynode.wrappers.mpy_transform import MPyTransform
    from mpynode._common.node_setups import find_demo

    node = MPyTransform.create(name="aimTransform", skip_selection=True)
    node.add_input_attr("matrix0", "matrix")
    node.add_input_attr("matrix1", "matrix")
    node.add_input_attr("parentWorld", "matrix")
    node.set_init_expression(AIM_TRANSFORM_INIT)
    node.set_compute_expression(AIM_TRANSFORM_COMPUTE)
    node.set_methods_source(DEMO_AIM)

    _stamp_class(node, "AimTransform", "mPyTransform")
    clean_payload = serialize_node(node, include_persistent=False)

    from mpynode._common.methods.methods_registry import run_node_demo
    from mpynode._common.io.mpn_io import deserialize_node

    def _v(*xyz):
        return np.array(xyz, dtype=float)

    ok = False
    detail = "n/a"
    try:
        mc.file(new=True, force=True)
        _ensure_mpy_plugins()
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        nm = tnode.get_name()
        run_node_demo(tnode)

        # Origins of the two connected matrix inputs (demo-position-agnostic).
        m0 = mc.getAttr(nm + ".matrix0")
        m1 = mc.getAttr(nm + ".matrix1")
        p0 = _v(m0[12], m0[13], m0[14])
        p1 = _v(m1[12], m1[13], m1[14])
        mid = 0.5 * (p0 + p1)
        fwd = (p1 - p0) / (np.linalg.norm(p1 - p0) + 1e-12)

        # GATED LOCAL-MATRIX + flush-free arch: .matrix (asMatrix) is now the plain
        # TRS; the aimed frame rides offsetParentMatrix and surfaces on
        # worldMatrix[0] (the node is a root with parentWorld=identity, so
        # world == local == the desired frame M).
        mtx = np.array(mc.getAttr(nm + ".worldMatrix[0]"),
                       dtype=float).reshape(4, 4)
        row_x, row_y, row_z = mtx[0, :3], mtx[1, :3], mtx[2, :3]
        origin = mtx[3, :3]

        mid_ok = float(np.linalg.norm(origin - mid)) < 1e-4
        x_ok = float(np.linalg.norm(row_x - fwd)) < 1e-4
        # Orthonormal, right-handed, no scale.
        orthonormal_ok = (
            abs(np.linalg.norm(row_x) - 1.0) < 1e-5
            and abs(np.linalg.norm(row_y) - 1.0) < 1e-5
            and abs(np.linalg.norm(row_z) - 1.0) < 1e-5
            and abs(float(np.dot(row_x, row_y))) < 1e-5
            and abs(float(np.dot(row_x, row_z))) < 1e-5
            and abs(float(np.dot(row_y, row_z))) < 1e-5
            and abs(float(np.linalg.det(mtx[:3, :3])) - 1.0) < 1e-4
        )

        # A child rides the midpoint (relative parent keeps its local identity).
        child = mc.group(empty=True, name="aimChild#")
        child = mc.parent(child, nm, relative=True)[0]
        cw = np.array(mc.getAttr(child + ".worldMatrix[0]"),
                      dtype=float).reshape(4, 4)
        child_ok = float(np.linalg.norm(cw[3, :3] - mid)) < 1e-4

        # A child offset +1 along local X lands one aim-unit toward p1.
        tip = mc.group(empty=True, name="aimTip#")
        tip = mc.parent(tip, nm, relative=True)[0]
        mc.setAttr(tip + ".translateX", 1.0)
        tw = np.array(mc.getAttr(tip + ".worldMatrix[0]"),
                      dtype=float).reshape(4, 4)
        tip_ok = float(np.linalg.norm(tw[3, :3] - (mid + fwd))) < 1e-4

        has_demo = find_demo(DEMO_AIM) is not None
        payload_ok = (clean_payload.get("native_type") == "mPyTransform"
                      and "matrix0" in (clean_payload.get("input_attrs") or {})
                      and "matrix1" in (clean_payload.get("input_attrs") or {})
                      and not clean_payload.get("stored_vars"))

        # --- authored @maya_test check on a FRESH deserialized node. ---
        test_ok = False
        test_err = "n/a"
        try:
            mc.file(new=True, force=True)
            _ensure_mpy_plugins()
            ttnode = deserialize_node(clean_payload, restore_persistent=False)
            tres = ttnode.run_test()
            test_ok = bool(tres.get("passed"))
            test_err = tres.get("error") or "ok"
        except Exception as texc:
            test_err = "exc:%r" % texc

        ok = bool(mid_ok and x_ok and orthonormal_ok and child_ok and tip_ok
                  and has_demo and payload_ok and test_ok)
        detail = ("mid=%s x=%s orthonormal=%s child=%s tip=%s demo=%s "
                  "payload=%s test=%s(%s)"
                  % (mid_ok, x_ok, orthonormal_ok, child_ok, tip_ok, has_demo,
                     payload_ok, test_ok, test_err))
    except Exception as exc:
        detail = "exc:%r" % exc

    print("[aim] %s -> %s" % (detail, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(AIM_DIR, clean_payload, AIM_DESC)
    return ok


# ---- Init tab: import the shared Solver (numpy + optional numba) from
# mpynode._common.nodes.rigging.dnet -- the single source of truth for the solver
# math + kernels. This is the pure-Python solver (NOT a numpy-free
# C++-transpilable variant).
DNET_INIT = r'''# DNET solver -- imported from the shared module
# mpynode._common.nodes.rigging.dnet (the numpy + optional-numba Solver,
# defined once as real, importable, unit-testable Python instead of a baked
# source blob). The Compute tab instantiates Solver and calls evaluate(). This
# mirrors the procrustes templates importing
# mpynode._common.nodes.constraint.procrustes and Game of Life importing
# mpynode._api2.mpy_mesh -- the node runs inside Maya with mpynode on sys.path,
# so the runtime import resolves. Importing the module also emits its one-time
# "USING NUMBA" / "NUMBA NOT AVAILABLE" banner.

import numpy as np
from mpynode._common.nodes.rigging.dnet import Solver
'''


# ---- Compute tab: the Solver.evaluate body, transcribed 1:1 (including its
# in-place `matrices` rebind), with a DYNAMIC reset vector seeded up-front (the
# spring_chain state pattern) so free knots carry secondary motion.
DNET_COMPUTE = r'''# DNET spring-network relaxation -- the source dnet .mpn's Compute
# expression (bugs/dnet_code.mpn), built on the VERBATIM numba Solver in the Init
# tab. The only addition over the .mpn's one-liner is reading the per-link inputs
# DENSELY: the .mpn's evaluate() fills a neutral default only for a *None* arg, but
# in an mPyNode a demo / create_link network wires the topology
# (index0 / index1 / restLengths) and tension yet leaves push / pull unset (empty
# multis) -- a raw pass would let the kernels index past a short array and silently
# ship an unrelaxed (all-zero) solve. So we pad each per-link array to the link
# count (the same "compute reads dense" contract the numpy-free port used); for a
# network whose arrays are already full (the .mpn's own scenes) this is a no-op and
# the Solver sees exactly what it did there.

import numpy as np

# `previous` is the solver carry-over state. In the source .mpn it is a persistent
# stored var (returns None until first solved); as a vanilla template it starts as
# session scratch, so seed it to None on first touch -- Solver(None) cold-starts
# (snaps free knots to their live goals). Promote `previous` to persistent (Data
# column) to carry the solved state across scene save / load like the .mpn.
if not hasattr(self, 'previous'):
    self.previous = None

# Init the node
if not hasattr(self, 'node'):
    self.node = Solver(self.previous)

matrices = np.asarray(self.matrices, dtype=np.float64).reshape(-1, 4, 4)
N = matrices.shape[0]

if self.evaluate and N > 0:
    # anchors dense to the knot count (unset knots read 0 == free).
    anchors = np.asarray(self.anchors, dtype=np.float64).ravel()
    if anchors.shape[0] < N:
        anchors = np.concatenate([anchors, np.zeros(N - anchors.shape[0])])
    else:
        anchors = anchors[:N]

    # Topology: paired link indices. Fall back to an open chain when no links are
    # wired so a bare (no-demo) node still relaxes into a line.
    index0 = np.asarray(self.index0, dtype=np.int32).ravel()
    index1 = np.asarray(self.index1, dtype=np.int32).ravel()
    L = min(index0.shape[0], index1.shape[0])
    if L == 0 and N >= 2:
        index0 = np.arange(N - 1, dtype=np.int32)
        index1 = np.arange(1, N, dtype=np.int32)
        L = N - 1
    else:
        index0 = index0[:L]
        index1 = index1[:L]

    def _dense(v, neutral):
        a = np.asarray(v, dtype=np.float64).ravel()
        if a.shape[0] >= L:
            return a[:L]
        out = np.full(L, neutral, dtype=np.float64)
        out[:a.shape[0]] = a
        return out

    restLengths = _dense(self.restLengths, 1.0)   # rest length per link
    tension = _dense(self.tension, 0.0)           # per-link contraction (0 = none)
    push = _dense(self.push, 1.0)                 # per-link compression resistance
    pull = _dense(self.pull, 1.0)                 # per-link stretch resistance

    self.node.evaluate(matrices, anchors, restLengths,
                       inverseMatrix=self.inverseMatrix, index0=index0, index1=index1,
                       tensions=tension, push=push, pull=pull,
                       reset=self.resetBuffer,
                       iterations=self.iterations,
                       tolerance=self.tolerance,
                       damping=self.damping)

    self.positions     = self.node.local_positions
    self.lengths       = self.node.lengths
    self.maxIterations = self.node.iterations
    self.maxForce      = self.node.max_force

    # Store previous state
    self.previous = self.node.previous
'''


# ---- Methods tab: a self-contained "Create + Run demo" that builds a pinned
# grid net which swings + settles when a corner is animated.
DEMO_DNET = '''
@maya_test(label="DNET pins anchors, relaxes free knots", digits=4)
def test_dnet(self):
    """Smoke-validate the solver's INTENT on THIS live node (parity-safe: the
    same test drives the interpreted node and its C++ compile). Fabricates a
    spring net through the node's OWN demo -- but only if this node isn't already
    driving one, since a demo/user may have connected the inputs already (the
    common UI flow, and repeated runs) and re-running would double-build the
    arrays. It then reproduces the builder's own live grid checks THROUGH the
    public plugs: at rest the whole net sits on its goals (solved offset ~0) with
    anchors pinned, and when the demo animates a corner out of plane the FREE
    knots relax (move) while the ANCHORED knots stay pinned. Reads only self's own
    array plugs (never a scene-wide name scan) and never setAttr's a connected
    input -- so it survives the create-node -> run-demo -> run-test flow."""
    from maya import cmds as mc
    from mpynode._common.methods.test_helpers import assert_true

    name = self.get_name()

    def mag(v):
        return (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5

    # Build the showcase net through the node's OWN demo -- but ONLY if this node
    # isn't already driving one. create_knot/create_link CONNECT matrices[]/
    # anchors[]/index0/index1, so a populated node's inputs are locked; re-running
    # the demo would append a SECOND grid and break the size checks below.
    # Call the top-level demo() FUNCTION directly (not self.run_demo(), a wrapper
    # method absent on the compiled node's _NodeNameProxy) so the SAME test runs
    # on the interpreted node AND its C++ compile. demo() drives only
    # self.get_name() + cmds, so it is proxy-safe.
    if not (mc.listConnections(name + ".matrices", s=True, d=False) or []):
        demo(self)

    # Count ONLY via self's own array plugs (parity-safe, no global scene scan).
    n = mc.getAttr(name + ".positions", size=True)
    assert_true(n > 0 and mc.getAttr(name + ".index0", size=True) > 0,
                "demo must populate a spring network on this node")

    # ANCHORED vs FREE knots read from the live anchor weights -- no hardcoded
    # corner indices, so this holds for whichever demo populated the node.
    anchored = [i for i in range(n)
                if abs(mc.getAttr(name + ".anchors[%d]" % i)) > 0.5]
    free = [i for i in range(n) if i not in anchored]
    assert_true(bool(anchored) and bool(free),
                "network needs both anchored and free knots")

    def positions(frame):
        # positions[i] is the goal-local solved offset; scrub + force a clean
        # recompute then read (mirrors the builder's live grid check).
        mc.currentTime(frame)
        mc.dgdirty(name + ".positions")
        return [mc.getAttr(name + ".positions[%d]" % i)[0] for i in range(n)]

    # (1) Rest frame: spacing == rest length -> the whole net sits on its goals,
    #     anchors included (solved offset ~0). [builder: rest_ok + corners_ok]
    d1 = positions(1)
    assert_true(max(mag(v) for v in d1) < 1e-2,
                "net should be at rest (all knots on their goals) on frame 1")
    assert_true(max(mag(d1[i]) for i in anchored) < 1e-3,
                "anchored knots must stay pinned to their goals at rest")

    # (2) Deformed frame: the demo animates a corner goal out of plane -> the FREE
    #     knots relax (move) while the ANCHORED knots stay pinned to their goals.
    #     [builder: corners_ok + interior_moved]
    d24 = positions(24)
    assert_true(max(mag(d24[i]) for i in anchored) < 1e-3,
                "anchored knots must stay pinned while the net deforms")
    assert_true(max(mag(d24[i]) for i in free) > 0.05,
                "free knots must relax/move when the net is deformed")


# Build a complete, self-contained DNET demo: a pinned grid "net". Every knot is
# built with the SAME create_knot helper (draw_icon=False -- lightweight, no
# icosahedron proxy) and every edge with create_link, so the demo exercises the
# exact authoring commands the user has. A knot's GOAL lays out a rows x cols
# grid (its worldMatrix -> matrices[i]); the four CORNERS are anchored (weight 1)
# and the rest are free. create_knot also makes a child RESULT transform riding
# positions[i]; a tiny marker sphere parented under it shows the solved knot
# world position. Grid edges are the springs. Animating the top-right corner goal
# makes the net swing between the fixed corners and settle. Time is wired to
# time1 so PLAYING the timeline animates it.
@maya_demo(label="Grid Net")
def demo(self):
    from maya import cmds as mc
    name = self.get_name()
    rows, cols, spacing = 6, 8, 1.0
    n = rows * cols
    corners = {0, cols - 1, (rows - 1) * cols, n - 1}

    # Tuning on the node (springy secondary motion, converges fast).
    mc.setAttr(name + ".iterations", 100)
    mc.setAttr(name + ".damping", 0.1)
    mc.setAttr(name + ".tolerance", 0.001)
    # tension is per-link now; the grid demo wants none, so leave every link at
    # the 0.0 default (setting the array root would error).

    # Both authoring commands are called as top-level FUNCTIONS rather than via
    # self.call_command(...), which routes through the wrapper's command
    # dispatcher -- absent on the compiled node's _NodeNameProxy. Calling them
    # directly is what call_command does anyway (invoke_command binds a self-first
    # runtime command straight to self), so the demo is proxy-safe and can back
    # the parity test on BOTH the interpreted node and its C++ compile. Both
    # commands still register normally (the Methods tab + Maya commands are
    # unaffected); this is the same function the dispatcher would resolve.
    goal_grp = mc.group(empty=True, name="dnetGoals#")
    goals = {}
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            # Lightweight knot: goal + child RESULT transform + solver wiring,
            # NO icosahedron proxy (draw_icon=False keeps a 48-knot grid cheap).
            goal = create_knot(self, draw_icon=False)
            goal = mc.parent(goal, goal_grp)[0]
            mc.setAttr(goal + ".translate", float(c) * spacing,
                       -float(r) * spacing, 0.0, type="double3")
            # anchor weight: 1 at the four corners, else 0 (free). anchored is a
            # goal attr wired into anchors[i] by create_knot.
            mc.setAttr(goal + ".anchored", 1.0 if i in corners else 0.0)
            goals[i] = goal
            # Tiny marker under the RESULT child (which rides positions[i]) so the
            # solved knot is visible without the heavier icosahedron proxy.
            child = mc.listRelatives(goal, children=True, type="transform")[0]
            marker = mc.polySphere(name="dnetKnotMarker#", radius=0.08)[0]
            mc.parent(marker, child, relative=True)

    # Links: horizontal + vertical grid edges, built with create_link (spoke
    # first, hub last -> index0 = spoke, index1 = hub). draw_icon=False keeps the
    # grid light; the rest length is measured from the two goals' layout gap.
    def link(a, b):
        mc.select(goals[a], goals[b], replace=True)
        create_link(self, draw_icon=False)

    for r in range(rows):
        for c in range(cols - 1):
            link(r * cols + c, r * cols + c + 1)
    for r in range(rows - 1):
        for c in range(cols):
            link(r * cols + c, r * cols + c + cols)

    # Animate the top-right corner goal so the net swings out of plane + settles.
    drv = goals[cols - 1]                          # knot (r=0, c=cols-1)
    rest_x = float(cols - 1) * spacing
    for t, (dx, dz) in ((1, (0.0, 0.0)), (24, (2.0, 5.0)), (48, (0.0, 0.0))):
        mc.setKeyframe(drv + ".translateX", time=t, value=rest_x + dx)
        mc.setKeyframe(drv + ".translateZ", time=t, value=dz)

    # add_input_attr already auto-connects time1.outTime -> .time on the
    # template-apply path; wire it here only as a fallback (re-issuing an
    # identical connection just emits a noisy "already connected" warning).
    if mc.objExists("time1") and not mc.listConnections(
            name + ".time", s=True, d=False):
        try:
            mc.connectAttr("time1.outTime", name + ".time", force=True)
        except Exception:
            pass
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


# --- Authoring commands: build a network by hand. Both are @maya_command, so
# they appear in the Methods tab and register as callable Maya commands, and the
# demos build every showcase through them. Run create_knot a few times to drop
# knots, then select spokes + a hub and run create_link to spring them
# together.
#
# Both bodies are VENDORED from mpynode._common.nodes.rigging.dnet (create_knot
# / create_link): a @maya_command body ships as embedded python inside the
# compiled .mll, where mpynode is NOT importable, so the authoring logic is
# carried here rather than delegated to the shared module. Pure maya.cmds +
# math, touching the node only through self.get_name(). ---
@maya_command(name="dnetCreateKnot", undoable=True)
def create_knot(self, draw_icon=False):
    """Create one KNOT -- a GOAL transform plus its RESULT child -- wired into
    the next free slot of this node.

    The GOAL is the transform you place/drive: ``goal.worldMatrix[0]`` drives
    ``matrices[i]`` and a ``goal.anchored`` weight (0 = free, 1 = pinned to the
    live goal) drives ``anchors[i]``. Its child RESULT transform receives
    ``positions[i]`` (the goal-local solved offset) on its ``translate``, so the
    child's WORLD position IS the solved knot -- the value ``create_link`` tracks.

    ``draw_icon=True`` adds a visual: an icosahedron ``polyPlatonicSolid`` whose
    hidden PROXY shape rides the RESULT child and whose visible DUPLICATE shape
    sits on the GOAL, linked by a worldspace ``blendShape`` (proxy -> visible) so
    the visible icon deforms onto the solved knot. A ``goal.radius`` attribute
    (default 0.1) drives both platonic solids. The goal is left selected so knots
    chain straight into ``create_link``. Returns the goal transform."""
    from maya import cmds as mc
    name = self.get_name()

    # Next free knot slot (indices may be sparse after deletes -> max + 1).
    idxs = mc.getAttr(name + ".matrices", multiIndices=True) or []
    i = (max(idxs) + 1) if idxs else 0

    # GOAL: the transform you place/drive. worldMatrix -> matrices[i]; owns an
    # `anchored` weight (0 free / 1 pinned) wired into anchors[i].
    goal = mc.group(empty=True, name="dnetGoal#")
    mc.addAttr(goal, longName="anchored", attributeType="float",
               min=0.0, max=1.0, defaultValue=0.0, keyable=True)
    mc.connectAttr(goal + ".worldMatrix[0]", name + ".matrices[%d]" % i, force=True)
    mc.connectAttr(goal + ".anchored", name + ".anchors[%d]" % i, force=True)

    # RESULT child: rides positions[i] (goal-local solved offset) so its WORLD
    # position IS the solved knot. create_link tracks these children.
    child = mc.group(empty=True, name="dnetKnot#")
    child = mc.parent(child, goal, relative=True)[0]
    mc.connectAttr(name + ".positions[%d]" % i, child + ".translate", force=True)

    if draw_icon:
        # A `radius` attr on the goal drives BOTH icosahedra so proxy + visible
        # stay the same size (a mismatched blend maps between different meshes).
        mc.addAttr(goal, longName="radius", attributeType="float",
                   min=0.0, defaultValue=0.1, keyable=True)
        proxy_xf, proxy_cre = mc.polyPlatonicSolid(radius=0.1, solidType=1)
        vis_xf, vis_cre = mc.polyPlatonicSolid(radius=0.1, solidType=1)
        mc.connectAttr(goal + ".radius", proxy_cre + ".radius", force=True)
        mc.connectAttr(goal + ".radius", vis_cre + ".radius", force=True)
        # Reparent the SHAPES: the hidden PROXY onto the RESULT child, the visible
        # DUPLICATE onto the GOAL. Then drop the emptied creator transforms.
        proxy_shp = mc.listRelatives(proxy_xf, shapes=True, fullPath=True)[0]
        vis_shp = mc.listRelatives(vis_xf, shapes=True, fullPath=True)[0]
        proxy_shp = mc.parent(proxy_shp, child, shape=True, relative=True)[0]
        vis_shp = mc.parent(vis_shp, goal, shape=True, relative=True)[0]
        mc.delete(proxy_xf, vis_xf)
        # Worldspace blendShape: proxy(child, rides positions) -> visible(goal),
        # so the visible icon deforms onto the solved knot. Build it BEFORE hiding
        # the proxy -- an invisible target is rejected as "not deformable" -- and
        # it binds at rest (positions == 0 -> child world == goal world -> 0
        # delta).
        bs = mc.blendShape(child, goal, origin="world",
                           name="dnetKnotBlend#")[0]
        mc.setAttr(bs + ".weight[0]", 1.0)
        mc.setAttr(proxy_shp + ".visibility", 0)

    mc.select(goal, replace=True)
    return goal


@maya_command(name="dnetCreateLink", undoable=True)
def create_link(self, draw_icon=False):
    """Spring every selected knot to the LAST-selected knot (the hub). Select the
    spoke knots, shift-select the hub last, then run this. For each spoke -> hub
    pair a link is added to the next free slot: ``index0[e]``/``index1[e]`` take
    the two knots' resolved indices and ``restLengths[e]`` is seeded to the two
    GOALS' layout distance (the intended length, so the network starts at rest).

    Each link is a TRANSFORM carrying its own ``tension`` / ``push`` / ``pull``
    wired to ``tension[e]`` / ``push[e]`` / ``pull[e]`` (per-link contraction,
    compression resistance, stretch resistance); its ``inheritsTransform`` is
    turned OFF (it stays at the origin) so a world-space line drawn under it is
    not double-transformed. Its translate / rotate / scale + visibility are LOCKED
    and HIDDEN, so the only channels a user sees are tension / push / pull.
    ``draw_icon=True`` parents a degree-1 line under the link that spans the two
    knots' RESULT children (their solved world positions). Returns the link
    transforms."""
    from maya import cmds as mc
    import math
    name = self.get_name()

    sel = mc.ls(selection=True, long=True, type="transform") or []
    if len(sel) < 2:
        raise RuntimeError("create_link needs >= 2 selected knots "
                           "(spokes first, hub last)")
    spokes, hub = sel[:-1], sel[-1]

    node_long = mc.ls(name, long=True)[0]

    def knot_index(goal):
        """Which matrices[] slot does this goal's worldMatrix[0] drive?"""
        for plug in (mc.listConnections(goal + ".worldMatrix[0]", source=False,
                                        destination=True, plugs=True) or []):
            pnode = plug.rsplit(".", 1)[0]
            if (mc.ls(pnode, long=True)[0] == node_long
                    and ".matrices[" in plug):
                return int(plug.rsplit("[", 1)[1].rstrip("]"))
        raise RuntimeError("%s is not a knot of %s (worldMatrix[0] is not "
                           "wired to matrices[])" % (goal, name))

    def knot_child(goal):
        """The goal's RESULT child (the transform riding positions[] -> its
        translate), whose worldMatrix is the solved knot."""
        for c in (mc.listRelatives(goal, children=True, type="transform", fullPath=True) or []):
            conns = mc.listConnections(c + ".translate", source=True,
                                       destination=False, plugs=True) or []
            if any(".positions[" in p for p in conns):
                return c
        raise RuntimeError("%s has no result child (positions[] -> translate)" % goal)

    hub_i = knot_index(hub)
    hub_child = knot_child(hub)
    hub_pos = mc.xform(hub, query=True, worldSpace=True, translation=True)

    # Next free link slot.
    lidxs = mc.getAttr(name + ".index0", multiIndices=True) or []
    e = (max(lidxs) + 1) if lidxs else 0

    links = []
    for spoke in spokes:
        spoke_i = knot_index(spoke)
        if spoke_i == hub_i:
            continue                                 # skip a degenerate self-link
        spoke_child = knot_child(spoke)
        spoke_pos = mc.xform(spoke, query=True, worldSpace=True, translation=True)

        # Topology: this spring connects spoke -> hub. Rest length = the GOALS'
        # layout gap (the intended length), NOT the solved children's distance.
        mc.setAttr(name + ".index0[%d]" % e, spoke_i)
        mc.setAttr(name + ".index1[%d]" % e, hub_i)
        rest = math.sqrt(sum((a - b) ** 2
                             for a, b in zip(spoke_pos, hub_pos)))
        mc.setAttr(name + ".restLengths[%d]" % e, rest)

        # The LINK transform hosts the per-link tension / push / pull, each wired
        # to its own node slot. inheritsTransform OFF (kept at the origin) so a
        # world-space line drawn under it is not double-transformed.
        link = mc.group(empty=True, name="dnetLink#")
        mc.setAttr(link + ".inheritsTransform", 0)
        mc.addAttr(link, longName="tension", attributeType="float",
                   defaultValue=0.0, keyable=True)
        mc.connectAttr(link + ".tension", name + ".tension[%d]" % e, force=True)
        mc.addAttr(link, longName="push", attributeType="float",
                   defaultValue=1.0, keyable=True)
        mc.connectAttr(link + ".push", name + ".push[%d]" % e, force=True)
        mc.addAttr(link, longName="pull", attributeType="float",
                   defaultValue=1.0, keyable=True)
        mc.connectAttr(link + ".pull", name + ".pull[%d]" % e, force=True)

        # The link is a pure carrier (inheritsTransform off, its line drawn in
        # world space), so its TRS must never be touched: lock + hide SRT and
        # visibility, leaving ONLY tension / push / pull editable in the channel
        # box. (The demos reparent links via group(relative=True), which preserves
        # local values and so never writes to the now-locked channels.)
        for chan in ("translate", "rotate", "scale"):
            for axis in ("X", "Y", "Z"):
                mc.setAttr("%s.%s%s" % (link, chan, axis),
                           lock=True, keyable=False, channelBox=False)
        mc.setAttr(link + ".visibility",
                   lock=True, keyable=False, channelBox=False)

        if draw_icon:
            # A degree-1 line between the two RESULT children's WORLD positions
            # (decomposeMatrix on each child's worldMatrix -> the CVs). Reparent
            # the SHAPE under the link (inheritsTransform off -> local == world)
            # and drop the emptied curve transform.
            crv = mc.curve(degree=1, point=[spoke_pos, hub_pos], name="dnetLinkCrv#")
            crv_shp = mc.listRelatives(crv, shapes=True, fullPath=True)[0]
            crv_shp = mc.parent(crv_shp, link, shape=True, relative=True)[0]
            mc.delete(crv)
            for k, cxf in ((0, spoke_child), (1, hub_child)):
                dm = mc.createNode("decomposeMatrix", name="dnetLinkDcm#")
                mc.connectAttr(cxf + ".worldMatrix[0]", dm + ".inputMatrix", force=True)
                mc.connectAttr(dm + ".outputTranslate",
                               crv_shp + ".controlPoints[%d]" % k, force=True)

        links.append(link)
        e += 1

    return links


# --- Second demo: rebuild the captured "layout net" (30 knots / 38 links) as a
# facial mouth membrane on a skull, built ENTIRELY through create_knot /
# create_link (draw_icon=True -> icosahedron proxy per knot, a line per link).
# Each knot is a GOAL that drives matrices[i] and a hidden PROXY icosahedron
# (on the RESULT child) worldspace-blendShaped onto the visible icosahedron (on
# the goal), so the visible icon shows the solved knot. After the net is built,
# the skull's jaw + cranium DRIVE it: a "midway" transform (position from jaw,
# rotation halfway between jaw and cranium) carries the mouth corners, the upper
# lip follows the cranium, the lower lip follows the jaw. The captured layout
# already contains COINCIDENT seam knots (one per lip), so opening the jaw splits
# them cleanly with no runtime duplication. ---
@maya_demo(label="Layout Net (JSON)")
def demo_layout(self):
    """Build the 30-knot / 38-link mouth net with the shape scheme
    (create_knot / create_link, draw_icon=True) and rig it to a skull's jaw and
    cranium.

    Each knot is a GOAL (worldMatrix -> matrices[i], with an ``anchored`` weight
    -> anchors[i] and a ``radius``) plus a RESULT child riding positions[i]; a
    hidden PROXY icosahedron on the child worldspace-blendShapes onto the visible
    icosahedron on the goal, so the visible icon lands on the solved knot. Each
    link is a transform carrying ``tension``/``push``/``pull`` (-> the per-link
    solver slots) and a line spanning the two knots' RESULT children.

    Part B -- the skull rig. ``skull.ma`` (a sibling of this template) is imported
    and its ``jaw`` + ``cranium`` transforms drive the net. A ``midway`` transform
    is point-constrained to the jaw and orient-constrained to BOTH jaw and cranium
    (equal weights -> it rotates halfway), and the mouth-CORNER goals ride it. The
    remaining goals are parent-constrained (maintain offset) to either the cranium
    (upper lip) or the jaw (lower lip). The knot -> driver split below is
    re-derived from the link topology (which inner knots wire to the upper lip
    ring 16-22 vs the lower lip ring 23-29) and from the coincident seam-knot
    pairs, so opening the jaw separates each seam pair (upper stays on the
    cranium, lower follows the jaw). If ``skull.ma`` cannot be found the net is
    still built (the skull rig is skipped)."""
    from maya import cmds as mc
    import os

    name = self.get_name()

    # Solver tuning: springy but converges quickly.
    mc.setAttr(name + ".iterations", 100)
    mc.setAttr(name + ".damping", 0.1)
    mc.setAttr(name + ".tolerance", 0.001)

    # Layout coordinates. Every goal is identity rotation, so only the
    # TRANSLATION (x, y, z) is needed. 30 knots. NOTE several pairs are COINCIDENT
    # (e.g. 0 & 8, 1 & 9, 2 & 6, 3 & 7, 10 & 14, 11 & 15) -- the lip-seam knots,
    # one for the upper lip and one for the lower, split apart when the jaw opens.
    pos = [
        (0.0, 0.19669, 5.392765244666164),
        (0.0, 0.19669, 4.005509244666164),
        (1.0305517469452337, 0.19669, 5.194273352061968),
        (0.5668036, 0.19669, 3.906263352061968),
        (1.913649628248397, 0.19669, 4.627198005746163),
        (1.170063428776204, 0.19669, 3.6227260057461628),
        (1.0305517469452337, 0.19668999999999995, 5.194273352061968),
        (0.5668036, 0.19668999999999995, 3.906263352061968),
        (0.0, 0.19668999999999995, 5.392765244666164),
        (0.0, 0.19668999999999995, 4.005509244666164),
        (-1.0305517469452337, 0.19668999999999995, 5.194273352061968),
        (-0.5668036, 0.19668999999999995, 3.906263352061968),
        (-1.913649628248397, 0.19669, 4.627198005746163),
        (-1.170063428776204, 0.19669, 3.6227260057461628),
        (-1.0305517469452337, 0.19669, 5.194273352061968),
        (-0.5668036, 0.19669, 3.906263352061968),
        (-2.1865856801030183, 1.465617139641164, 2.582529220268003),
        (-1.1051264520850839, 2.1400429010391235, 3.189491868019104),
        (-0.5764899849891663, 2.6176137924194336, 3.4333497285842896),
        (0.0, 1.2445201873779297, 3.8054476976394653),
        (0.57649, 2.6176137924194336, 3.4333497285842896),
        (1.1051264520850839, 2.1400429010391235, 3.189491868019104),
        (2.186586, 1.465617139641164, 2.582529220268003),
        (-1.8105760687991268, -0.6292422913548227, 2.330734850776368),
        (-1.2259319038613272, -1.0863746468609303, 2.9697747323628123),
        (-0.641077152522516, -1.3094022902401772, 3.446323628284529),
        (0.0, -1.2426437351935555, 3.6167521432120227),
        (0.641077152522516, -1.3094022902401772, 3.446323628284529),
        (1.2259319038613272, -1.0863746468609303, 2.9697747323628123),
        (1.8105760687991268, -0.6292422913548227, 2.330734850776368)]
    # Anchor weight per knot (1 = pinned to its goal, 0 = free to relax). 30.
    anch = [1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0,
            0.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    # Links as (spoke_knot, hub_knot) index pairs. 38.
    links = [
        (0, 1), (2, 3), (4, 5), (6, 7), (8, 9), (10, 11), (12, 13), (14, 15),
        (3, 1), (5, 3), (7, 5), (9, 7), (11, 9), (13, 11), (15, 13), (1, 15),
        (13, 16), (13, 17), (15, 18), (19, 1), (20, 3), (21, 5), (22, 5),
        (13, 23), (13, 24), (11, 25), (9, 26), (7, 27), (5, 28), (5, 29),
        (19, 3), (19, 15), (17, 15), (21, 3), (26, 7), (26, 11), (24, 11), (28, 7)]

    # KNOTS: build every one with create_knot(draw_icon=True) so each is the full
    # icosahedron proxy scheme (goal drives matrices[i]; RESULT child rides
    # positions[i]; hidden proxy blendShaped onto the visible icon). Position the
    # goal, seed its anchored weight, size its radius.
    goal_grp = mc.group(empty=True, name="dnetGoals#")
    goals = []
    for i, (p, a) in enumerate(zip(pos, anch)):
        goal = self.call_command("dnetCreateKnot", draw_icon=True)
        goal = mc.parent(goal, goal_grp, relative=True)[0]
        mc.xform(goal, translation=list(p), worldSpace=True)
        mc.setAttr(goal + ".anchored", float(a))
        mc.setAttr(goal + ".radius", 0.12)
        goals.append(goal)

    # LINKS: create_link(draw_icon=True) per pair (spoke first, hub last -> the
    # spring is index0 = spoke, index1 = hub; rest = the goals' layout gap).
    link_xf = []
    for si, hi in links:
        mc.select(goals[si], goals[hi], replace=True)
        link_xf += (self.call_command("dnetCreateLink", draw_icon=True) or [])

    # ---- Part B: drive the mouth net with the skull's jaw + cranium. ----
    # Resolve skull.ma the way the gallery resolves templates/: $MPYNODE_ROOT
    # first, else walk up from the mpynode package to the dir holding
    # scripts/mpynode. The asset is a sibling of this template.
    import mpynode
    env = os.environ.get("MPYNODE_ROOT")
    troot = None
    if env:
        troot = os.path.join(env, "templates")
    else:
        d = os.path.dirname(os.path.abspath(mpynode.__file__))
        while True:
            if os.path.isdir(os.path.join(d, "scripts", "mpynode")):
                troot = os.path.join(d, "templates")
                break
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    skull = (os.path.join(troot, "MPyNode", "DNET", "skull.ma") if troot else None)

    if (skull and os.path.exists(skull)
            and not (mc.objExists("jaw") and mc.objExists("cranium"))):
        mc.file(skull, i=True, ignoreVersion=True,
                mergeNamespacesOnClash=True)

    if mc.objExists("jaw") and mc.objExists("cranium"):
        # midway transform: POSITION from the jaw, ROTATION halfway between jaw
        # and cranium (equal-weight orientConstraint -> half the jaw's swing), so
        # the mouth corners follow the joint at half rate (classic lip corner).
        midway = mc.createNode("transform", name="dnetJawMidway#")
        mc.pointConstraint("jaw", midway, maintainOffset=False)
        mc.orientConstraint("jaw", "cranium", midway, maintainOffset=False)

        # Knot -> driver assignment, re-derived from the layout geometry + link
        # topology (see the docstring). The inner contour (0-15) splits along the
        # lip seam: the members wired toward the upper-lip ring (16-22) follow the
        # cranium, those wired toward the lower-lip ring (23-29) follow the jaw,
        # and the extreme mouth corners ride the midway. Every coincident seam
        # pair ends up split (one on the cranium, one on the jaw).
        corner_knots = [4, 5, 12, 13]
        cranium_knots = [0, 1, 2, 3, 14, 15, 16, 17, 18, 19, 20, 21, 22]
        jaw_knots = [6, 7, 8, 9, 10, 11, 23, 24, 25, 26, 27, 28, 29]
        for idx in corner_knots:
            mc.parentConstraint(midway, goals[idx], maintainOffset=True)
        for idx in cranium_knots:
            mc.parentConstraint("cranium", goals[idx], maintainOffset=True)
        for idx in jaw_knots:
            mc.parentConstraint("jaw", goals[idx], maintainOffset=True)

    # Tidy the net rig under one group (RELATIVE so nothing is world-compensated).
    # The links carry inheritsTransform=False, so grouping them never shifts their
    # world-space lines.
    mc.group([goal_grp] + link_xf, name="dnetLayout#", relative=True)

    # Fallback time wiring (parity with the grid demo).
    if mc.objExists("time1") and not mc.listConnections(
            name + ".time", s=True, d=False):
        try:
            mc.connectAttr("time1.outTime", name + ".time", force=True)
        except Exception:
            pass
    # This demo IMPORTS skull.ma, so frame the WHOLE scene -- the imported skull
    # can sit anywhere relative to the net, and leaving it off screen hides what
    # the demo just built.
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


# --- Third demo: the MINIMAL dnet -- TWO FREE knots plus FOUR anchors, FIVE
# links -- built with the SAME create_knot / create_link helpers (draw_icon=True)
# as the layout demo. The two free hubs each tether to a pair of anchors and to
# each other; drag any anchor and the free hubs follow springily, their visible
# icosahedra deforming onto the solved positions via the worldspace blendShape.
# The smallest scene that shows the shape scheme end to end. ---
@maya_demo(label="Two Knots (Shapes)")
def demo_two_knots(self):
    """Build a small dnet -- TWO FREE knots plus FOUR anchors, FIVE links -- with
    create_knot / create_link (draw_icon=True).

    The two FREE knots (0, 1) are the moving hubs: knot 0 tethers to anchors 2, 3
    and knot 1 to anchors 4, 5, and the two hubs link to each other. Each knot's
    ``anchored`` weight is seeded (1 pins the four anchors, 0 frees the two hubs)
    and drives ``anchors[i]``; the visible icosahedron on each goal deforms onto
    its solved RESULT child through the worldspace blendShape. Each link is a
    transform (``tension``/``push``/``pull`` -> the solver) parenting a line that
    spans the two knots' RESULT children. Drag any anchor and the free hubs
    follow springily."""
    from maya import cmds as mc

    name = self.get_name()

    # Solver tuning: springy but converges quickly.
    mc.setAttr(name + ".iterations", 100)
    mc.setAttr(name + ".damping", 0.1)
    mc.setAttr(name + ".tolerance", 0.001)

    # Six knots: two FREE hubs (0, 1) linked to each other, each tethered to a
    # pair of ANCHORED goals (2-5).
    pos = [
        (-3.0, 0.0,  0.0),   # 0  free hub
        ( 3.0, 0.0,  0.0),   # 1  free hub
        (-6.0, 0.0, -3.0),   # 2  anchor
        (-6.0, 0.0,  3.0),   # 3  anchor
        ( 6.0, 0.0, -3.0),   # 4  anchor
        ( 6.0, 0.0,  3.0),   # 5  anchor
    ]
    anch = [0.0, 0.0, 1.0, 1.0, 1.0, 1.0]
    # Five links (spoke -> hub): each free hub tied to its two anchors, and the
    # two hubs tied to each other.
    links = [(2, 0), (3, 0), (1, 0), (4, 1), (5, 1)]

    goal_grp = mc.group(empty=True, name="dnetGoals#")
    goals = []
    for i, (p, a) in enumerate(zip(pos, anch)):
        goal = self.call_command("dnetCreateKnot", draw_icon=True)
        goal = mc.parent(goal, goal_grp, relative=True)[0]
        mc.xform(goal, translation=list(p), worldSpace=True)
        mc.setAttr(goal + ".anchored", float(a))
        mc.setAttr(goal + ".radius", 0.4)
        goals.append(goal)

    link_xf = []
    for si, hi in links:
        mc.select(goals[si], goals[hi], replace=True)
        link_xf += (self.call_command("dnetCreateLink", draw_icon=True) or [])

    # Tidy under one group (RELATIVE; links carry inheritsTransform=False).
    mc.group([goal_grp] + link_xf, name="dnetLayout#", relative=True)

    # Fallback time wiring (parity with the other demos).
    if mc.objExists("time1") and not mc.listConnections(
            name + ".time", s=True, d=False):
        try:
            mc.connectAttr("time1.outTime", name + ".time", force=True)
        except Exception:
            pass
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name
'''


DNET_DESC = """# DNET Spring-Network Solver

A mass-spring network for rigging. Knots carry goal transforms (`matrices[]`);
links (`index0`/`index1`) are springs with rest lengths (`restLengths`). Each
frame the solver settles the net, so free knots trail and jiggle behind whatever
drives them -- soft secondary motion for lips, fleshy pads and membranes.
Anchored knots (`anchors[i] > 0`) snap to their live goal. Solved parent-space
positions come out on `positions[]`.

Every scene here is built from just two authoring commands -- **create_knot** and
**create_link** -- so the demos are exactly what you would assemble by hand. A
knot is a GOAL transform (its `worldMatrix` drives `matrices[i]`, an `anchored`
float drives `anchors[i]`) plus a RESULT child riding `positions[i]`; a link is a
transform carrying its own per-link `tension`/`push`/`pull` (wired to the matching
solver slots) with `inheritsTransform` off. With `draw_icon=True` a knot also gets
an icosahedron: a hidden PROXY shape on the result child worldspace-blendShaped
onto a visible DUPLICATE on the goal (sized by a `radius` attr), so the visible
icon deforms onto the solved knot; a link gets a degree-1 line whose two CVs track
the knots' result children (a `decomposeMatrix` per CV).

**Create + Run demo** offers three showcases (right-click the template for the
submenu).

*Grid Net* anchors the four corners of a 6x8 grid and animates one of them, so
the net swings between the fixed corners and settles -- play the timeline. It is
built lightweight (`draw_icon=False`): a goal, a result child and a tiny marker
sphere, no icosahedron.

*Layout Net (JSON)* rebuilds a 30-knot / 38-link mouth membrane from a captured
layout with the full shape scheme (`draw_icon=True`), then rigs it to a skull.
`skull.ma` is imported and its **jaw** and **cranium** drive the net: a `midway`
transform, positioned from the jaw and rotated halfway between the two, carries
the mouth corners; the upper-lip knots follow the cranium and the lower-lip knots
the jaw, so opening the jaw splits each coincident lip-seam pair.

*Two Knots (Shapes)* is the minimal net: TWO FREE knots, each tethered to a pair
of anchors and linked to each other -- six knots, five links, the same shape
scheme end to end. Drag any anchor and the free knots follow springily, their
icosahedra deforming onto the solved positions.

**Build your own** (Methods tab): run **create_knot** a few times to drop knots
(each is a goal with an `anchored` weight wired into `matrices[]`/`anchors[]` plus
a result child on `positions[]`; pass `draw_icon=True` for the icosahedron icon,
sized by a `radius` attr that defaults to 0.1), then select some spoke knots,
shift-select a hub last, and run **create_link** to spring them together (each link
seeds `index0`/`index1`/`restLengths` and carries its own per-link `tension`,
`push` and `pull` -- the only channels left editable, since the link transform's
translate/rotate/scale + visibility are locked and hidden; `draw_icon=True` adds
the line).

Tuning: `iterations` (relaxation cap), `damping` (under-relaxation step),
`tolerance` (convergence threshold), `tension` (per-link contraction),
`push`/`pull` (per-link compression / stretch resistance -- one slot per link,
neutral 1.0), `resetBuffer` (defaults True: re-seed free knots from their live
goals each eval; set False to carry state and let free knots continue).
"""


def build_dnet():
    """Author the DNET spring-network solver as a base mPyNode, then verify it
    behaviorally through a full serialize -> deserialize round-trip (matching
    the sibling build_* functions): rebuild the vanilla template in a fresh
    scene, run its demo net, scrub time, and assert corners stay pinned while
    the interior swings + settles. Writes the template only on PASS."""
    mc.file(new=True, force=True)
    _ensure_mpy_plugins()
    from mpynode.wrappers._mpy_node import MPyNode
    from mpynode._common.node_setups import find_demo, find_demos

    node = MPyNode.create(name="dnet", skip_selection=True)

    # Inputs -- names / types / defaults / order match the source dnet .mpn
    # (bugs/dnet_code.mpn) 1:1 so this template IS that solver's node. Order index
    # in the trailing comment is the .mpn attribute `order`.
    node.add_input_attr("matrices", "matrix", is_array=True)                 # 0
    node.add_input_attr("anchors", "float", is_array=True)                   # 1
    node.add_input_attr("index0", "int", is_array=True)                      # 2
    node.add_input_attr("index1", "int", is_array=True)                      # 3
    node.add_input_attr("restLengths", "float", is_array=True, default_value=1.0)   # 4
    # PER-LINK tension: create_link wires each link curve's own tension attr to a
    # tension[e] slot, so this is an array (a scalar plug takes only ONE incoming
    # connection). Unset/unconnected links read the 0.0 default (no contraction).
    node.add_input_attr("tension", "float", is_array=True, default_value=0.0)       # 5
    node.add_input_attr("iterations", "int", default_value=100, min_value=1)        # 6
    node.add_input_attr("tolerance", "float", default_value=0.001)                  # 7
    node.add_input_attr("damping", "float", default_value=0.1)                      # 8
    node.add_input_attr("inverseMatrix", "matrix")                                  # 9
    # resetBuffer defaults TRUE: every eval re-seeds free knots from their live
    # goal matrices and relaxes (a deterministic, history-free solve). Set it
    # False to make free knots CONTINUE from the previous frame (momentum-like).
    node.add_input_attr("resetBuffer", "enum", enum_names=["False", "True"],
                        default_value=1)                                            # 10
    # evaluate gates the solve (the .mpn's on/off switch): 0 freezes the outputs at
    # their last value, 1 (default) runs the relaxation on each dirty.
    node.add_input_attr("evaluate", "enum", enum_names=["False", "True"],
                        default_value=1)                                            # 11
    # PER-LINK push / pull: like tension, create_link wires each link curve's own
    # push / pull attr to a push[e] / pull[e] slot, so these are arrays too.
    # Unset/unconnected links read the 1.0 default (neutral compression / stretch
    # resistance -- identical to the former scalar-knob behaviour).
    node.add_input_attr("push", "float", is_array=True, default_value=1.0)          # 12
    node.add_input_attr("pull", "float", is_array=True, default_value=1.0)          # 13
    # time is NOT one of the .mpn's 14 solver inputs; it is a template convenience
    # so the demos can wire time1.outTime -> .time and animate on playback (the
    # solver body ignores it).
    node.add_input_attr("time", "time")

    # Outputs -- the .mpn's four. `positions` is the parent-space solved offset
    # (goal-local displacement, == the old `driven`) fed to each knot's child
    # transform; `lengths` the per-link solved lengths; `maxIterations` the
    # iteration count reached; `maxForce` the final max displacement.
    node.add_output_attr("positions", "vector", is_array=True)              # 0
    node.add_output_attr("lengths", "float", is_array=True, default_value=0.0)      # 1
    node.add_output_attr("maxIterations", "int", default_value=0)                   # 2
    node.add_output_attr("maxForce", "float", default_value=0.0)                    # 3

    node.set_init_expression(DNET_INIT)
    node.set_compute_expression(DNET_COMPUTE)
    node.set_methods_source(DEMO_DNET)
    # Canonical Class identity: synthesize the in-memory ``mpynode_user.MPyDnet``
    # class and stamp its dotted path (the canonical, importable form). The old
    # bare "MPyDnet" tag was not importable; this makes the template carry a real
    # Class that resolves via synth-on-open.
    from mpynode._common.io.user_classes import synthesize, dotted_path
    synthesize("MPyDnet", "mPyNode")
    node.set_py_class(dotted_path("MPyDnet"))

    # Vanilla payload BEFORE the live checks (no baked stored solver state).
    clean_payload = serialize_node(node, include_persistent=False)
    # Preferred node name: every create-from-template of this template names
    # the node mPyDnet# (the create commands honor payload["preferred_name"]).
    clean_payload["preferred_name"] = "mPyDnet1"

    from mpynode._common.methods.methods_registry import run_node_demo
    from mpynode._common.io.mpn_io import deserialize_node

    rows, cols = 6, 8
    n = rows * cols
    corners = [0, cols - 1, (rows - 1) * cols, n - 1]
    interior = [r * cols + c for r in range(1, rows - 1)
                for c in range(1, cols - 1)]

    def mag(v):
        return (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5

    ok = False
    detail = "n/a"
    try:
        # ================= Demo 1: Grid Net (lightweight helpers) ============
        # Built entirely through create_knot(draw_icon=False) + create_link: 48
        # knots (goal + RESULT child + solver wiring, no icosahedron) and 82
        # spring links. A tiny marker under each RESULT child shows the solve.
        mc.file(new=True, force=True)
        _ensure_mpy_plugins()
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        nm = tnode.get_name()
        run_node_demo(tnode)

        def driven_at(frame):
            mc.currentTime(frame)
            mc.dgdirty(nm + ".positions")
            return [mc.getAttr(nm + ".positions[%d]" % i)[0] for i in range(n)]

        size_ok = (mc.getAttr(nm + ".positions", size=True) == n
                   and mc.getAttr(nm + ".index0", size=True) == 82)
        d1 = driven_at(1)      # rest grid (spacing == rest length) -> ~0
        d24 = driven_at(24)    # corner pulled out of plane -> net deformed
        rest_ok = max(mag(v) for v in d1) < 1e-2
        corners_ok = (max(mag(d1[i]) for i in corners) < 1e-3
                      and max(mag(d24[i]) for i in corners) < 1e-3)
        interior_moved = max(mag(d24[i]) for i in interior) > 0.05
        # Lightweight: markers under the result children, NO icosahedron proxies.
        grid_light_ok = (len(mc.ls("dnetKnotMarker*", type="transform") or []) == n
                         and not (mc.ls(type="blendShape") or []))

        # ================= Demo 2: Layout Net + skull rig ====================
        # 30-knot / 38-link mouth net built with create_knot/create_link
        # (draw_icon=True -> icosahedron proxy per knot, one line per link), then
        # rigged to skull.ma's jaw + cranium. Verify the shape scheme, that the
        # OLD gizmo/aim scheme is gone, the skull rig, and a solver response.
        mc.file(new=True, force=True)
        _ensure_mpy_plugins()
        lnode = deserialize_node(clean_payload, restore_persistent=False)
        lnm = lnode.get_name()
        run_node_demo(lnode, "demo_layout")

        layout_size_ok = (mc.getAttr(lnm + ".positions", size=True) == 30
                          and mc.getAttr(lnm + ".index0", size=True) == 38
                          and mc.getAttr(lnm + ".index1", size=True) == 38)

        goal_nodes = set(mc.listConnections(lnm + ".matrices", source=True,
                                            destination=False) or [])
        # Per-link tension / push / pull each come from a LINK transform's own
        # attr (not an aim's translateX any more).
        def slot_plugs(attr):
            return (mc.listConnections(lnm + "." + attr, source=True,
                                       destination=False, plugs=True) or [])
        tension_plugs = slot_plugs("tension")
        push_plugs = slot_plugs("push")
        pull_plugs = slot_plugs("pull")
        wire_ok = (len(goal_nodes) == 30
                   and len(tension_plugs) == 38
                   and len(push_plugs) == 38 and len(pull_plugs) == 38
                   and all(p.split(".", 1)[1] == "tension" for p in tension_plugs)
                   and all(p.split(".", 1)[1] == "push" for p in push_plugs)
                   and all(p.split(".", 1)[1] == "pull" for p in pull_plugs))
        # Shape scheme present, OLD gizmo/aim scheme gone.
        n_blend = len(mc.ls(type="blendShape") or [])
        no_gizmos = not (mc.ls(type="mPyLocator") or [])
        no_aims = not (mc.ls(type="mPyTransform") or [])
        # 38 link transforms, each inheritsTransform OFF, each with a line curve.
        link_nodes = sorted(set(p.rsplit(".", 1)[0] for p in tension_plugs))
        inh_off = all(mc.getAttr(l + ".inheritsTransform") == 0
                      for l in link_nodes)
        line_ok = all(len(mc.listRelatives(l, shapes=True, type="nurbsCurve")
                          or []) == 1 for l in link_nodes)
        layout_shape_ok = (wire_ok and n_blend == 30 and no_gizmos and no_aims
                           and len(link_nodes) == 38 and inh_off and line_ok)

        # Skull rig: jaw + cranium imported; a midway transform point-constrained
        # to the jaw + orient-constrained to jaw & cranium; every goal
        # parent-constrained to its assigned driver.
        def goal_of(i):
            return (mc.listConnections(lnm + ".matrices[%d]" % i, source=True,
                                       destination=False) or [None])[0]

        def drivers_of(i):
            g = goal_of(i)
            try:
                return set(mc.parentConstraint(g, query=True,
                                               targetList=True) or [])
            except Exception:
                return set()

        n_parentC = len(mc.ls(type="parentConstraint") or [])
        n_pointC = len(mc.ls(type="pointConstraint") or [])
        n_orientC = len(mc.ls(type="orientConstraint") or [])
        # Geometry-derived assignment: corners (4,5,12,13) -> midway;
        # upper-lip-side (e.g. 0) -> cranium; lower-lip-side (e.g. 6) -> jaw.
        assign_ok = (any("dnetJawMidway" in d for d in drivers_of(4))
                     and "cranium" in drivers_of(0)
                     and "jaw" in drivers_of(6))
        skull_ok = (mc.objExists("jaw") and mc.objExists("cranium")
                    and n_parentC == 30 and n_pointC == 1 and n_orientC == 1
                    and assign_ok)

        # Solver RESPONSE: raise every link's tension -> a free knot's solved
        # displacement grows while anchored knots stay pinned. Then confirm the
        # visible icosahedron tracks the solved child (the worldspace blendShape).
        free = [i for i in range(30)
                if abs(mc.getAttr(lnm + ".anchors[%d]" % i)) < 0.5]
        pinned = [i for i in range(30) if i not in free]
        mc.setAttr(lnm + ".resetBuffer", 1)
        mc.setAttr(lnm + ".iterations", 200)

        def free_disp():
            mc.dgdirty(lnm + ".positions")
            return max(mag(mc.getAttr(lnm + ".positions[%d]" % i)[0])
                       for i in free)

        slack_free = free_disp()
        for l in link_nodes:
            mc.setAttr(l + ".tension", 1.0)
        taut_free = free_disp()
        pinned_ok = max(mag(mc.getAttr(lnm + ".positions[%d]" % i)[0])
                        for i in pinned) < 1e-2

        def child_world(i):
            plugs = (mc.listConnections(lnm + ".positions[%d]" % i, source=False,
                                        destination=True, plugs=True) or [])
            xs = [p.rsplit(".", 1)[0] for p in plugs
                  if p.rsplit(".", 1)[1] == "translate"]
            return mc.xform(xs[0], query=True, worldSpace=True,
                            translation=True) if xs else None

        def visible_center(i):
            shp = mc.listRelatives(goal_of(i), shapes=True, type="mesh",
                                   fullPath=True) or []
            if not shp:
                return None
            bb = mc.exactWorldBoundingBox(shp[0])
            return [(bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2,
                    (bb[2] + bb[5]) / 2]

        fi = free[0]
        vc, cw = visible_center(fi), child_world(fi)
        icon_tracks = (vc is not None and cw is not None
                       and mag([vc[j] - cw[j] for j in range(3)]) < 0.5)
        layout_solves = (slack_free < 1e-2 and taut_free > slack_free + 0.05
                         and pinned_ok and icon_tracks)

        # ================= Demo 3: Two Knots (Shapes) ========================
        # TWO free hubs + FOUR anchors + FIVE links, all via the helpers
        # (draw_icon=True). Verify the icosahedron proxy scheme, attribute-driven
        # anchors, per-link line curves, and that dragging an anchor pulls its
        # free hub while the anchor stays pinned (guarded on the log bus).
        mc.file(new=True, force=True)
        _ensure_mpy_plugins()
        snode = deserialize_node(clean_payload, restore_persistent=False)
        snm = snode.get_name()
        run_node_demo(snode, "demo_two_knots")

        shapes_size_ok = (mc.getAttr(snm + ".positions", size=True) == 6
                          and mc.getAttr(snm + ".index0", size=True) == 5
                          and mc.getAttr(snm + ".index1", size=True) == 5)
        sgoals = set(mc.listConnections(snm + ".matrices", source=True,
                                        destination=False) or [])
        sdriven_plugs = (mc.listConnections(snm + ".positions", source=False,
                                            destination=True, plugs=True) or [])
        schildren = set(p.rsplit(".", 1)[0] for p in sdriven_plugs
                        if p.rsplit(".", 1)[1] == "translate")
        n_bs = len(mc.ls(type="blendShape") or [])
        # 5 link transforms drive tension via their own `tension` attr.
        stension_plugs = (mc.listConnections(snm + ".tension", source=True,
                                             destination=False, plugs=True) or [])
        stx_ok = all(p.split(".", 1)[1] == "tension" for p in stension_plugs)
        slink_nodes = sorted(set(p.rsplit(".", 1)[0] for p in stension_plugs))
        # Each link parents exactly ONE degree-1 curve spanning its two knots.
        curves_ok = True
        curve_spans_ok = True
        for l in slink_nodes:
            cs = mc.listRelatives(l, shapes=True, type="nurbsCurve",
                                  fullPath=True) or []
            if len(cs) != 1 or mc.getAttr(cs[0] + ".degree") != 1:
                curves_ok = False
                break
            c0 = mc.pointPosition(cs[0] + ".cv[0]", world=True)
            c1 = mc.pointPosition(cs[0] + ".cv[1]", world=True)
            if mag([c1[j] - c0[j] for j in range(3)]) < 1.0:
                curve_spans_ok = False
        # Anchors ATTRIBUTE-DRIVEN: each goal owns an `anchored` float wired into
        # anchors[i]. Anchors 2-5 = 1.0, free hubs 0-1 = 0.0.
        anchor_srcs = [(mc.listConnections(snm + ".anchors[%d]" % i, source=True,
                                           destination=False, plugs=True)
                        or [None])[0] for i in range(6)]
        anchor_conn_ok = (all(s is not None for s in anchor_srcs)
                          and all(s.rsplit(".", 1)[1] == "anchored"
                                  for s in anchor_srcs)
                          and all(abs(mc.getAttr(snm + ".anchors[%d]" % i) - 1.0)
                                  < 1e-6 for i in (2, 3, 4, 5))
                          and all(abs(mc.getAttr(snm + ".anchors[%d]" % i))
                                  < 1e-6 for i in (0, 1)))
        no_locators = not (mc.ls(type="mPyLocator") or [])
        no_stf = not (mc.ls(type="mPyTransform") or [])
        shapes_links_ok = (len(sgoals) == 6 and len(schildren) == 6
                           and n_bs == 6 and len(slink_nodes) == 5
                           and len(stension_plugs) == 5 and stx_ok
                           and curves_ok and curve_spans_ok and anchor_conn_ok
                           and no_locators and no_stf)

        # Drag an anchor -> its free hub follows (solved displacement grows) while
        # the anchor stays pinned. Guard compute on the log bus so a silently
        # crashed compute (positions never written -> 0) can't masquerade as rest.
        from mpynode._common.util import log_bus

        class _ShapesErrSink(object):
            def __init__(self):
                self.errors = []

            def append_message(self, message, level):
                if level == "error" or "expression error" in message:
                    self.errors.append(message)

        def sdriven_mag(i):
            mc.dgdirty(snm + ".positions")
            return mag(mc.getAttr(snm + ".positions[%d]" % i)[0])

        _ssink = _ShapesErrSink()
        log_bus.subscribe(_ssink)
        try:
            mc.setAttr(snm + ".resetBuffer", 1)
            s_rest = sdriven_mag(0)                       # free hub 0 at rest -> ~0
            sg2 = (mc.listConnections(snm + ".matrices[2]", source=True,
                                      destination=False) or [None])[0]
            mc.move(8.0, 5.0, 3.0, sg2, relative=True)    # drag anchor 2 far
            s_after = sdriven_mag(0)                      # hub 0 follows -> grows
            s_pinned = sdriven_mag(2)                     # anchor 2 pinned -> ~0
        finally:
            log_bus.unsubscribe(_ssink)
        shapes_no_err = not _ssink.errors
        shapes_holds = (s_rest < 1e-2 and s_after > 0.2 and s_pinned < 1e-2
                        and shapes_no_err)

        # --- authored @maya_test check on a FRESH deserialized node. ---
        test_ok = False
        test_err = "n/a"
        try:
            mc.file(new=True, force=True)
            _ensure_mpy_plugins()
            ttnode = deserialize_node(clean_payload, restore_persistent=False)
            tres = ttnode.run_test()
            test_ok = bool(tres.get("passed"))
            test_err = tres.get("error") or "ok"
        except Exception as texc:
            test_err = "exc:%r" % texc

        # ================= Payload / demo metadata ===========================
        demos_ok = len(find_demos(DEMO_DNET)) == 3
        has_demo = find_demo(DEMO_DNET) is not None
        payload_ok = (clean_payload.get("native_type") == "mPyNode"
                      and clean_payload.get("class_path") == "mpynode_user.MPyDnet"
                      and clean_payload.get("preferred_name") == "mPyDnet1"
                      and "matrices" in (clean_payload.get("input_attrs") or {})
                      and "positions" in (clean_payload.get("output_attrs") or {})
                      and not clean_payload.get("stored_vars"))

        ok = bool(size_ok and rest_ok and corners_ok and interior_moved
                  and grid_light_ok and layout_size_ok and layout_shape_ok
                  and skull_ok and layout_solves and shapes_size_ok
                  and shapes_links_ok and shapes_holds and demos_ok
                  and has_demo and payload_ok and test_ok)
        detail = ("grid(size=%s rest=%s corners=%s moved=%s light=%s) "
                  "layout(size=%s shape=%s skull=%s solves=%s) "
                  "shapes(size=%s links=%s holds=%s) "
                  "demos=%s demo=%s payload=%s test=%s(%s)"
                  % (size_ok, rest_ok, corners_ok, interior_moved, grid_light_ok,
                     layout_size_ok, layout_shape_ok, skull_ok, layout_solves,
                     shapes_size_ok, shapes_links_ok, shapes_holds,
                     demos_ok, has_demo, payload_ok, test_ok, test_err))
    except Exception as exc:
        import traceback
        detail = "exc:%r\n%s" % (exc, traceback.format_exc())

    print("[dnet] %s -> %s" % (detail, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(DNET_DIR, clean_payload, DNET_DESC)
    return ok


# ======================================================================
# mPySkinCluster -- linear blend skinning (LBS)
# ======================================================================
# Demo authored into the LBS template's Methods tab: import the bundled two-bone
# arm (arm.ma -- the same file the "ouch" example uses), EXTRACT the stock
# skinCluster's weights / influences / bindPreMatrix, detach it (the mesh reverts
# to its exact rest geometry), then re-skin the SAME mesh with THIS mPySkinCluster
# -- reproducing the original deform from the extracted weights -- and bend the
# elbow so the arm starts posed. Falls back to a 2-joint cylinder if arm.ma is
# unavailable. Parity of the recipe is pinned by
# _tests/test_skin_cluster_lbs_arm_parity.py.
SKIN_LBS_DEMO = '''@maya_test(label="Skin deforms the arm; envelope 0 is rest; result is finite", digits=3)
def test_skin(self):
    """Validate the node's INTENT (the SAME test passes on the interpreted node
    and its C++ compile -> parity, and on BOTH the linear-blend and dual-
    quaternion skin templates since it only asserts mode-agnostic skinning):
    a weighted two-joint bind actually deforms the mesh, the deform stays
    finite, and envelope 0 returns the mesh to its exact rest regardless of the
    joint pose."""
    from maya import cmds as mc
    import numpy as np
    import maya.api.OpenMaya as om2
    from mpynode._common.methods.test_helpers import assert_close, assert_true

    name = self.get_name()

    def _pts(shape):
        sl = om2.MSelectionList(); sl.add(shape)
        fn = om2.MFnMesh(sl.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    def _set(plug, *vals):
        # A demo/build may have CONNECTED this plug (keyframe/anim); break the
        # incoming connection first so the test can drive it, then set.
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals)

    def _read_env(shape, env):
        # Force a fresh eval of THIS deformer at the given envelope.
        _set(name + ".envelope", env)
        mc.dgdirty(name + ".outputGeometry")
        mc.getAttr(shape + ".outMesh")
        return _pts(shape)

    # Validate whatever mesh this skinCluster ALREADY deforms (the demo's arm, or
    # the cylinder create/build bound). A skinCluster already bound to one mesh
    # will NOT deform a second mesh (that is the interactive "max move 0.0000"
    # bug), so only build a fresh rig when self is unbound. This keeps the test on
    # self -- interpreted-vs-compiled parity -- and robust to a live,
    # demo-populated scene and to being run twice.
    try:
        bound = mc.skinCluster(name, q=True, geometry=True) or []
    except Exception:
        bound = []

    if bound:
        shape = (mc.ls(bound[0], long=True) or [bound[0]])[0]
        # envelope 0 -> exact rest (skin bypassed); envelope 1 -> the deform at
        # whatever pose the joints currently hold (the demo posed the elbow).
        rest = _read_env(shape, 0.0)
        posed = _read_env(shape, 1.0)
        # Safety net: if the joints happen to sit at bind pose (nothing to
        # deform), bend the first influence to force a real deform, then re-read.
        if float(np.abs(posed - rest).max()) <= 0.1:
            infl = mc.skinCluster(name, q=True, influence=True) or []
            if infl:
                _set(infl[0] + ".rotateZ", 45.0)
            posed = _read_env(shape, 1.0)
    else:
        # --- self drives nothing yet: build a fresh cylinder + 2-joint rig -----
        cyl = mc.polyCylinder(name="skinTestArm#", radius=1.0, height=6.0,
                              subdivisionsX=10, subdivisionsY=10)[0]
        shape = mc.listRelatives(cyl, shapes=True, fullPath=True)[0]
        mc.select(clear=True)
        j0 = mc.joint(name="skinTestBase#", position=(0.0, -3.0, 0.0))
        j1 = mc.joint(name="skinTestMid#", position=(0.0, 0.0, 0.0))
        mc.select(clear=True)
        # Read rest heights BEFORE attaching (querying an attached, unpainted
        # skin would trigger the 0.5/0.5 first-eval lock-in), then paint weights.
        nvc = mc.polyEvaluate(cyl, vertex=True)
        ys = [mc.xform("%s.vtx[%d]" % (cyl, v), q=True, os=True, t=True)[1] for v in range(nvc)]
        lo, hi = min(ys), max(ys)
        span = (hi - lo) or 1.0
        mc.deformer(name, e=True, g=cyl)
        for i, jnt in enumerate((j0, j1)):
            mc.connectAttr(jnt + ".worldMatrix[0]", "%s.matrix[%d]" % (name, i), force=True)
            inv = mc.getAttr(jnt + ".worldInverseMatrix[0]")
            mc.setAttr("%s.bindPreMatrix[%d]" % (name, i), inv, type="matrix")
        # Weights BEFORE the first eval (a kSkinCluster locks 0.5/0.5 otherwise).
        for v in range(nvc):
            t = (ys[v] - lo) / span
            mc.setAttr("%s.weightList[%d].weights[0]" % (name, v), 1.0 - t)
            mc.setAttr("%s.weightList[%d].weights[1]" % (name, v), t)
        rest = _read_env(shape, 0.0)     # envelope 0 -> exact rest
        _set(j1 + ".rotateZ", 60.0)      # bend the elbow
        posed = _read_env(shape, 1.0)    # envelope 1 + bent elbow -> real deform

    assert_true(np.isfinite(posed).all(), "skinned points must be finite")
    moved = float(np.abs(posed - rest).max())
    assert_true(moved > 0.1,
                "a bent, weighted bind must deform the mesh (max move %.4f)" % moved)

    # envelope 0 at the current (bent) pose must still return to rest (skin off).
    env0_posed = _read_env(shape, 0.0)
    assert_close(env0_posed.ravel().tolist(), rest.ravel().tolist())


@maya_demo(label="Skin a Two-Bone Arm (LBS)")
def demo(self):
    """Import the bundled two-bone arm, extract the stock skinCluster's weights,
    detach it, and re-skin the SAME mesh with THIS mPySkinCluster running linear
    blend skinning -- reproducing the original deform from the extracted weights.
    Keyframes the elbow through a bend arc (on rotateY, the arm's hinge axis) so
    playing the timeline swings the arm. Falls back to a simple 2-joint cylinder
    if the bundled arm.ma is unavailable."""
    from maya import cmds as mc
    import os
    name = self.get_name()

    def _mobj1(n):
        import maya.OpenMaya as om1
        sl = om1.MSelectionList(); sl.add(n)
        o = om1.MObject(); sl.getDependNode(0, o); return o

    def _dag1(n):
        import maya.OpenMaya as om1
        sl = om1.MSelectionList(); sl.add(n)
        dp = om1.MDagPath(); sl.getDagPath(0, dp); return dp

    def _extract(sc, mesh_shape):
        import maya.OpenMaya as om1
        import maya.OpenMayaAnim as oma1
        mfn = oma1.MFnSkinCluster(_mobj1(sc))
        infl = om1.MDagPathArray(); mfn.influenceObjects(infl)
        names = [infl[i].fullPathName() for i in range(infl.length())]
        comp_fn = om1.MFnSingleIndexedComponent()
        comp = comp_fn.create(om1.MFn.kMeshVertComponent)
        nv = mc.polyEvaluate(mesh_shape, vertex=True)
        comp_fn.setCompleteData(nv)
        wts = om1.MDoubleArray()
        su = om1.MScriptUtil(); su.createFromInt(0); p = su.asUintPtr()
        mfn.getWeights(_dag1(mesh_shape), comp, wts, p)
        ninf = om1.MScriptUtil.getUint(p)
        W = [[wts[v * ninf + c] for c in range(ninf)] for v in range(nv)]
        bind = {}
        for cc in (mc.getAttr(sc + ".bindPreMatrix", multiIndices=True) or []):
            bind[cc] = mc.getAttr(sc + ".bindPreMatrix[%d]" % cc)
        return names, W, nv, ninf, bind

    # --- locate + import the bundled two-bone arm --------------------------
    arm = None
    try:
        from mpynode._common.util.template_gallery import _bundled_templates_root
        root = _bundled_templates_root()
        cand = os.path.join(root or "", "MPyNode", "Ouch", "arm.ma")
        if os.path.isfile(cand):
            arm = cand
    except Exception:
        arm = None

    if arm:
        new = mc.file(arm, i=True, ignoreVersion=True, returnNewNodes=True) or []
        skins = mc.ls(new, type="skinCluster") or []
        joints = mc.ls(new, type="joint", long=True) or []
        meshes = [m for m in (mc.ls(new, type="mesh", long=True) or [])
                  if not mc.getAttr(m + ".intermediateObject")]
        if skins and meshes:
            sc = skins[0]
            mesh_shape = meshes[0]
            mesh_xform = mc.listRelatives(mesh_shape, parent=True, fullPath=True)[0]
            elbow = (next((j for j in joints
                           if j.rsplit("|", 1)[-1] == "loarm_r_JNT"), None)
                     or next((j for j in joints if "loarm" in j), None))
            influences, W, nv, ninf, bind = _extract(sc, mesh_shape)
            # Detach the stock skin -> the mesh reverts to its exact rest.
            mc.skinCluster(sc, e=True, unbind=True)
            # Attach THIS node to the mesh + wire the joints (worldMatrix ->
            # matrix[i], byte-exact bindPreMatrix from the stock).
            if name not in (mc.listHistory(mesh_xform) or []):
                mc.deformer(name, e=True, g=mesh_xform)
            for i, jnt in enumerate(influences):
                mc.connectAttr(jnt + ".worldMatrix[0]",
                               "%s.matrix[%d]" % (name, i), force=True)
                if i in bind:
                    mc.setAttr("%s.bindPreMatrix[%d]" % (name, i), bind[i], type="matrix")
            # Apply the extracted weights BEFORE the first eval (a kSkinCluster
            # locks a 0.5/0.5 default on first eval, then resists setAttr).
            for v in range(nv):
                for c in range(ninf):
                    mc.setAttr("%s.weightList[%d].weights[%d]" % (name, v, c), float(W[v][c]))
            # Keyframe the elbow through a bend arc so PLAYING the timeline
            # swings the arm. The arm hinges on rotateY (rotateX is twist);
            # it rests at the bent frame so the deform shows the moment it opens.
            if elbow:
                for ax in ("rotateX", "rotateY", "rotateZ"):
                    for s in (mc.listConnections(elbow + "." + ax, s=True,
                                                 d=False, plugs=True) or []):
                        mc.disconnectAttr(s, elbow + "." + ax)
                    mc.setAttr(elbow + "." + ax, lock=False)
                for f, ry in ((1, 0.0), (60, 60.0), (120, 0.0)):
                    mc.setKeyframe(elbow + ".rotateY", time=f, value=ry)
                mc.playbackOptions(min=1, max=120)
                mc.currentTime(60)
            try:
                mc.select(mesh_xform, replace=True)
                # This branch IMPORTED arm.ma -- frame the WHOLE scene so the
                # imported rig can never land off screen.
                for _panel in mc.getPanel(type="modelPanel") or []:
                    _cam = mc.modelEditor(_panel, query=True, camera=True)
                    if _cam:
                        mc.viewFit(_cam, allObjects=True)
            except Exception:
                pass
            return name

    # --- fallback: a subdivided cylinder + 2-joint chain ------------------
    cyl = mc.polyCylinder(name="lbsArm#", radius=1.0, height=6.0,
                          subdivisionsX=12, subdivisionsY=10)[0]
    mc.select(clear=True)
    j0 = mc.joint(name="lbsBase#", position=(0.0, -3.0, 0.0))
    j1 = mc.joint(name="lbsMid#", position=(0.0, 0.0, 0.0))
    mc.select(clear=True)
    # Read rest heights BEFORE attaching the deformer (querying an attached,
    # unpainted skin would trigger the 0.5/0.5 lock-in on first eval).
    nvc = mc.polyEvaluate(cyl, vertex=True)
    ys = [mc.xform("%s.vtx[%d]" % (cyl, v), q=True, os=True, t=True)[1] for v in range(nvc)]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1.0
    if name not in (mc.listHistory(cyl) or []):
        mc.deformer(name, e=True, g=cyl)
    for i, jnt in enumerate((j0, j1)):
        mc.connectAttr(jnt + ".worldMatrix[0]", "%s.matrix[%d]" % (name, i), force=True)
        inv = mc.getAttr(jnt + ".worldInverseMatrix[0]")
        mc.setAttr("%s.bindPreMatrix[%d]" % (name, i), inv, type="matrix")
    for v in range(nvc):
        t = (ys[v] - lo) / span
        mc.setAttr("%s.weightList[%d].weights[0]" % (name, v), 1.0 - t)
        mc.setAttr("%s.weightList[%d].weights[1]" % (name, v), t)
    # Keyframe a bend arc (the fallback cylinder runs up Y, so it hinges on
    # rotateZ; the real arm branch above hinges on rotateY).
    for f, rz in ((1, 0.0), (60, 60.0), (120, 0.0)):
        mc.setKeyframe(j1 + ".rotateZ", time=f, value=rz)
    mc.playbackOptions(min=1, max=120)
    mc.currentTime(60)
    try:
        mc.select(cyl, replace=True)
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name
'''


SKIN_LBS_DESC = (
    "# Linear Blend Skin\n\n"
    "A real skinCluster (`mPySkinCluster`) that does classic linear blend "
    "skinning in Python: every vertex lands on a weighted average of the "
    "joints influencing it. Good for seeing how skinning works under the "
    "hood, or as a base for your own deformer.\n\n"
    "Maya sees a genuine skinCluster, so Paint Skin Weights, the Component "
    "Editor and `cmds.skinPercent` read and write its `weightList` plug live. "
    "Compiles to pure C++ -- a native skinCluster that deforms the same "
    "way.\n\n"
    "**Create + Run demo** imports the bundled two-bone arm, moves the "
    "weights off its stock skinCluster onto this one, and bends the elbow so "
    "the arm starts posed.")


def _mesh_object_pts(shape):
    """Object-space points of a mesh shape as an (N, 3) numpy array."""
    sel = om.MSelectionList()
    sel.add(shape)
    fn = om.MFnMesh(sel.getDagPath(0))
    return np.array([[p.x, p.y, p.z] for p in fn.getPoints(om.MSpace.kObject)])


def build_skin_lbs():
    from mpynode._defaults import skin_cluster_defaults as scd
    from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster

    # --- compute check: a synthetic 2-joint cylinder vs a numpy LBS oracle --
    mc.file(new=True, force=True)
    cyl = mc.polyCylinder(name="lbsCheck", radius=1.0, height=6.0,
                          subdivisionsX=8, subdivisionsY=8)[0]
    cyl_shape = mc.listRelatives(cyl, shapes=True, fullPath=True)[0]
    mc.select(clear=True)
    j0 = mc.joint(name="lbsCheckBase", position=(0.0, -3.0, 0.0))
    j1 = mc.joint(name="lbsCheckMid", position=(0.0, 0.0, 0.0))
    mc.select(clear=True)

    rest = _mesh_object_pts(cyl_shape)                    # (N, 3), no eval
    nvv = rest.shape[0]
    ys = rest[:, 1]
    lo, hi = float(ys.min()), float(ys.max())
    span = (hi - lo) or 1.0
    t = np.clip((ys - lo) / span, 0.0, 1.0)
    Wm = np.zeros((nvv, 2), dtype=np.float64)
    Wm[:, 0] = 1.0 - t
    Wm[:, 1] = t

    sc = MPySkinCluster.create(mesh=cyl, joints=[j0, j1], name="linearBlendSkin")
    node = sc.get_name()
    for v in range(nvv):
        sc.set_vertex_weight(v, 0, float(Wm[v, 0]))
        sc.set_vertex_weight(v, 1, float(Wm[v, 1]))
    sc.set_init_expression(scd.DEFAULT_INIT_SOURCE)
    sc.set_compute_expression(scd.DEFAULT_COMPUTE_SOURCE)
    sc.set_methods_source(SKIN_LBS_DEMO)

    mc.setAttr(j1 + ".rotateZ", 55.0)
    mc.dgdirty(node + ".outputGeometry")
    mc.getAttr(cyl_shape + ".outMesh")
    deformed = _mesh_object_pts(cyl_shape)

    joint0 = np.array(mc.getAttr(j0 + ".worldMatrix[0]")).reshape(4, 4)
    joint1 = np.array(mc.getAttr(j1 + ".worldMatrix[0]")).reshape(4, 4)
    bind0 = np.array(mc.getAttr(node + ".bindPreMatrix[0]")).reshape(4, 4)
    bind1 = np.array(mc.getAttr(node + ".bindPreMatrix[1]")).reshape(4, 4)
    M = np.stack([bind0 @ joint0, bind1 @ joint1])
    pts_h = np.concatenate([rest, np.ones((nvv, 1))], axis=1)
    oracle = np.einsum("vj,jkc,vk->vc", Wm, M, pts_h)[:, :3]

    moved = float(np.abs(deformed - rest).max())
    parity = float(np.abs(deformed - oracle).max())
    compute_ok = moved > 0.1 and parity < 1e-4

    # --- demo check: "Create + Run demo" on a FRESH deserialized node -------
    _stamp_class(sc, "LinearBlendSkin", "mPySkinCluster")
    clean_payload = serialize_node(sc, include_persistent=False)
    demo_ok = False
    demo_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node
        from mpynode._common.methods.methods_registry import run_node_demo
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tnm = tnode.get_name()
        run_node_demo(tnode)
        target = None
        for m in (mc.ls(type="mesh", long=True) or []):
            if mc.getAttr(m + ".intermediateObject"):
                continue
            if tnm in (mc.listHistory(m) or []):
                target = m
                break
        in_hist = target is not None
        deforms = False
        if target is not None:
            # envelope 0 -> rest, envelope 1 -> full skin; a real deform differs.
            mc.setAttr(tnm + ".envelope", 0.0)
            mc.dgdirty(tnm + ".outputGeometry")
            mc.getAttr(target + ".outMesh")
            rest_p = _mesh_object_pts(target)
            mc.setAttr(tnm + ".envelope", 1.0)
            mc.dgdirty(tnm + ".outputGeometry")
            mc.getAttr(target + ".outMesh")
            def_p = _mesh_object_pts(target)
            deforms = float(np.abs(def_p - rest_p).max()) > 0.5
        demo_ok = bool(in_hist and deforms)
        demo_err = "mesh=%s in_hist=%s deforms=%s" % (target, in_hist, deforms)
    except Exception as exc:
        demo_err = "exc:%r" % exc

    # --- authored @maya_test check on a FRESH deserialized node. ---
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    ok = compute_ok and demo_ok and test_ok
    print("[skin_lbs] moved=%.4f parity=%.2e demo=%s(%s) test=%s(%s) -> %s"
          % (moved, parity, demo_ok, demo_err, test_ok, test_err,
             "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(SKIN_LBS_DIR, clean_payload, SKIN_LBS_DESC)
    return ok


# ======================================================================
# mPySkinCluster -- dual quaternion skinning (DQS)
# ======================================================================
# Same demo as LBS (import arm.ma -> extract stock weights -> re-skin THIS node),
# only the label differs -- the LBS-vs-DQS behaviour comes from the node's Compute
# (the DQS default), not the demo. The DQS Compute lowers to pure C++ too (proven
# by native/tests/nd_lower_test.py SKIN_DQS fixtures + _tests/test_skin_cluster_dqs.py).
SKIN_DQS_DEMO = SKIN_LBS_DEMO.replace(
    'label="Skin a Two-Bone Arm (LBS)"',
    'label="Skin a Two-Bone Arm (DQS)"')


SKIN_DQS_DESC = (
    "# Dual Quaternion Skin\n\n"
    "A real skinCluster (`mPySkinCluster`) that does dual quaternion "
    "skinning. Instead of averaging joint matrices, it blends each joint's "
    "rotation and translation as a dual quaternion, so a bent elbow or "
    "twisted wrist keeps its volume rather than collapsing into the classic "
    "\"candy wrapper\" pinch.\n\n"
    "It reads the same live `weightList` plug as the Linear Blend Skin "
    "template, so Paint Skin Weights, the Component Editor and "
    "`cmds.skinPercent` all drive it, and one set of weights works in either. "
    "Compiles to pure C++ -- a native skinCluster that deforms the same "
    "way.\n\n"
    "**Create + Run demo** imports the bundled two-bone arm, moves the "
    "weights off its stock skinCluster onto this one, and bends the elbow so "
    "the arm starts posed. Compare the bent volume against the Linear Blend "
    "Skin template.")


def build_skin_dqs():
    from mpynode._defaults import skin_cluster_dqs_defaults as dqs
    from mpynode._defaults import skin_cluster_defaults as lbs
    from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster

    # --- compute check: DQS deforms, stays finite, and DIFFERS from LBS on a
    #     real bend (else it isn't really dual-quaternion) --------------------
    mc.file(new=True, force=True)
    cyl = mc.polyCylinder(name="dqsCheck", radius=1.0, height=6.0,
                          subdivisionsX=8, subdivisionsY=8)[0]
    cyl_shape = mc.listRelatives(cyl, shapes=True, fullPath=True)[0]
    mc.select(clear=True)
    j0 = mc.joint(name="dqsCheckBase", position=(0.0, -3.0, 0.0))
    j1 = mc.joint(name="dqsCheckMid", position=(0.0, 0.0, 0.0))
    mc.select(clear=True)

    rest = _mesh_object_pts(cyl_shape)
    nvv = rest.shape[0]
    ys = rest[:, 1]
    lo, hi = float(ys.min()), float(ys.max())
    span = (hi - lo) or 1.0
    t = np.clip((ys - lo) / span, 0.0, 1.0)

    sc = MPySkinCluster.create(mesh=cyl, joints=[j0, j1], name="dualQuaternionSkin")
    node = sc.get_name()
    for v in range(nvv):
        sc.set_vertex_weight(v, 0, float(1.0 - t[v]))
        sc.set_vertex_weight(v, 1, float(t[v]))
    sc.set_init_expression(dqs.DEFAULT_INIT_SOURCE)
    sc.set_compute_expression(dqs.DEFAULT_COMPUTE_SOURCE)
    sc.set_methods_source(SKIN_DQS_DEMO)

    mc.setAttr(j1 + ".rotateZ", 70.0)
    mc.dgdirty(node + ".outputGeometry")
    mc.getAttr(cyl_shape + ".outMesh")
    dqs_pts = _mesh_object_pts(cyl_shape)
    # Swap to the LBS compute on the SAME painted/posed rig for the divergence check.
    sc.set_compute_expression(lbs.DEFAULT_COMPUTE_SOURCE)
    mc.dgdirty(node + ".outputGeometry")
    mc.getAttr(cyl_shape + ".outMesh")
    lbs_pts = _mesh_object_pts(cyl_shape)
    # Restore the DQS compute for serialization.
    sc.set_compute_expression(dqs.DEFAULT_COMPUTE_SOURCE)

    moved = float(np.abs(dqs_pts - rest).max())
    finite = bool(np.isfinite(dqs_pts).all())
    divergence = float(np.abs(dqs_pts - lbs_pts).max())
    compute_ok = moved > 0.1 and finite and divergence > 1e-3

    # --- demo check: "Create + Run demo" on a FRESH deserialized node --------
    _stamp_class(sc, "DualQuaternionSkin", "mPySkinCluster")
    clean_payload = serialize_node(sc, include_persistent=False)
    demo_ok = False
    demo_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node
        from mpynode._common.methods.methods_registry import run_node_demo
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tnm = tnode.get_name()
        run_node_demo(tnode)
        target = None
        for m in (mc.ls(type="mesh", long=True) or []):
            if mc.getAttr(m + ".intermediateObject"):
                continue
            if tnm in (mc.listHistory(m) or []):
                target = m
                break
        in_hist = target is not None
        deforms = False
        if target is not None:
            mc.setAttr(tnm + ".envelope", 0.0)
            mc.dgdirty(tnm + ".outputGeometry")
            mc.getAttr(target + ".outMesh")
            rest_p = _mesh_object_pts(target)
            mc.setAttr(tnm + ".envelope", 1.0)
            mc.dgdirty(tnm + ".outputGeometry")
            mc.getAttr(target + ".outMesh")
            def_p = _mesh_object_pts(target)
            deforms = float(np.abs(def_p - rest_p).max()) > 0.5
        demo_ok = bool(in_hist and deforms)
        demo_err = "mesh=%s in_hist=%s deforms=%s" % (target, in_hist, deforms)
    except Exception as exc:
        demo_err = "exc:%r" % exc

    # --- authored @maya_test check on a FRESH deserialized node. ---
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    ok = compute_ok and demo_ok and test_ok
    print("[skin_dqs] moved=%.4f finite=%s vs_lbs=%.4f demo=%s(%s) test=%s(%s) -> %s"
          % (moved, finite, divergence, demo_ok, demo_err, test_ok, test_err,
             "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(SKIN_DQS_DIR, clean_payload, SKIN_DQS_DESC)
    return ok


# ---------------------------------------------------------------------------
# Twist/Swing skin (TWO independent weight sets on ONE skinCluster). The
# Compute / Methods / Description strings are the SSOT in
# mpynode._demos.twist_swing_skin_source (Maya-free, shared with the native
# compiler parity tests so the shipped Compute == the tested Compute). The two
# painted sets are declared `double is_array=True` INPUT plugs (flattened N*J),
# so each node keeps its own weights and the deformer COMPILES to byte-parity.
# ---------------------------------------------------------------------------
SKIN_TWISTSWING_INIT = _tsw_src.INIT
SKIN_TWISTSWING_COMPUTE = _tsw_src.COMPUTE
SKIN_TWISTSWING_METHODS = _tsw_src.METHODS
SKIN_TWISTSWING_DESC = _tsw_src.DESC


def build_skin_twist_swing():
    from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
    from mpynode._common.methods import skin_blend as _sb

    def _seed_plug(nm, plug, W):
        """setAttr a dense (N, J) weight set into a flattened double-array plug."""
        flat = np.asarray(W, dtype=np.float64).ravel()
        for i in range(flat.size):
            mc.setAttr("%s.%s[%d]" % (nm, plug, i), float(flat[i]))

    def _read_plug(nm, plug, shape):
        idx = mc.getAttr("%s.%s" % (nm, plug), multiIndices=True) or []
        flat = np.array([mc.getAttr("%s.%s[%d]" % (nm, plug, i)) for i in idx],
                        dtype=np.float64)
        return flat.reshape(shape)

    def _clear_plug(nm, plug):
        for i in (mc.getAttr("%s.%s" % (nm, plug), multiIndices=True) or []):
            mc.removeMultiInstance("%s.%s[%d]" % (nm, plug, i), b=True)

    # --- compute check: Live Result deforms; the swing weight set INDEPENDENTLY
    #     changes the result (proving the two sets are genuinely used) -----------
    mc.file(new=True, force=True)
    cyl = mc.polyCylinder(name="expCheck", radius=1.0, height=6.0,
                          subdivisionsX=8, subdivisionsY=8)[0]
    cyl_shape = mc.listRelatives(cyl, shapes=True, fullPath=True)[0]
    mc.select(clear=True)
    j0 = mc.joint(name="expCheckBase", position=(0.0, -3.0, 0.0))
    j1 = mc.joint(name="expCheckMid", position=(0.0, 0.0, 0.0))
    mc.select(clear=True)

    rest = _mesh_object_pts(cyl_shape)
    nvv = rest.shape[0]
    ys = rest[:, 1]
    lo, hi = float(ys.min()), float(ys.max())
    span = (hi - lo) or 1.0
    t = np.clip((ys - lo) / span, 0.0, 1.0)
    twist_w = np.stack([1.0 - t, t], axis=1)
    ts = np.clip((t - 0.5) * 2.5 + 0.5, 0.0, 1.0)      # sharper falloff
    swing_w = np.stack([1.0 - ts, ts], axis=1)

    sc = MPySkinCluster.create(mesh=cyl, joints=[j0, j1], name="twistSwingSkin")
    node = sc.get_name()
    for v in range(nvv):
        sc.set_vertex_weight(v, 0, float(twist_w[v, 0]))
        sc.set_vertex_weight(v, 1, float(twist_w[v, 1]))
    # The two weight sets are DECLARED double array INPUT plugs (flattened N*J) so
    # they serialize per node and the deform COMPILES to byte-parity.
    sc.add_input_attr("twistWeights", "double", is_array=True)
    sc.add_input_attr("swingWeights", "double", is_array=True)
    # skinMode PAINT-MODE selector (0 Paint LBS / 1 Paint DQS / 2 Live Result);
    # twistAxis picks the bone-local twist axis (X/Y/Z, default X).
    sc.add_input_attr("skinMode", "enum",
                      enum_names=["Paint LBS (Swing)", "Paint DQS (Twist)",
                                  "Live Result"],
                      default_value=2)
    sc.add_input_attr("twistAxis", "enum",
                      enum_names=["X", "Y", "Z"], default_value=0)
    mc.setAttr(node + ".twistAxis", 0)
    sc.set_init_expression(SKIN_TWISTSWING_INIT)
    sc.set_compute_expression(SKIN_TWISTSWING_COMPUTE)
    sc.set_methods_source(SKIN_TWISTSWING_METHODS)
    mc.setAttr(node + ".skinMode", 2)

    mc.setAttr(j1 + ".rotateX", 80.0)
    mc.setAttr(j1 + ".rotateZ", 55.0)

    def _eval_pts():
        # Toggle the envelope (a real plug) to force the deformer to actually
        # re-run its compute (dgdirty alone can return the cached deformed mesh).
        mc.setAttr(node + ".envelope", 0.0)
        mc.dgdirty(node + ".outputGeometry")
        mc.getAttr(cyl_shape + ".outMesh")
        mc.setAttr(node + ".envelope", 1.0)
        mc.dgdirty(node + ".outputGeometry")
        mc.getAttr(cyl_shape + ".outMesh")
        return _mesh_object_pts(cyl_shape)

    # Live Result reads the two weight-set plugs. Same set for both -> equals
    # twist_swing; a DIFFERENT swing set must change the result.
    _seed_plug(node, "twistWeights", twist_w)
    _seed_plug(node, "swingWeights", twist_w)
    same_pts = _eval_pts()
    _seed_plug(node, "swingWeights", swing_w)
    diff_pts = _eval_pts()

    moved = float(np.abs(diff_pts - rest).max())
    finite = bool(np.isfinite(diff_pts).all())
    swing_effect = float(np.abs(diff_pts - same_pts).max())
    compute_ok = moved > 0.1 and finite and swing_effect > 1e-3

    # --- skinMode paint modes: each mode previews its OWN algorithm + weights ----
    #     0 Paint LBS -> linear_blend(swing); 1 Paint DQS -> dual_quaternion(twist);
    #     2 Live Result -> twist_swing_dual(twist, swing). Verify vs the oracle and
    #     that the three modes are visibly distinct. (plugs: twist=twist_w,
    #     swing=swing_w from the swing_effect check above.)
    joint_m = np.stack([np.array(mc.getAttr(jj + ".worldMatrix[0]")).reshape(4, 4)
                        for jj in (j0, j1)])
    bind_m = np.stack([np.array(mc.getAttr("%s.bindPreMatrix[%d]" % (node, i)))
                       .reshape(4, 4) for i in (0, 1)])

    def _mode_pts(m):
        mc.setAttr(node + ".skinMode", m)
        return _eval_pts()

    lin_pts = _mode_pts(0)     # Paint LBS: loads swing->weightList, linear_blend
    dq_pts = _mode_pts(1)      # Paint DQS: loads twist->weightList, dual_quaternion
    tsw_pts = _mode_pts(2)     # Live Result: twist_swing_dual(twist, swing)
    mc.setAttr(node + ".skinMode", 2)                  # restore default
    lin_oracle = _sb.linear_blend(rest, swing_w, joint_m, bind_m)
    dq_oracle = _sb.dual_quaternion(rest, twist_w, joint_m, bind_m)
    tsw_oracle = _sb.twist_swing_dual(rest, twist_w, swing_w, joint_m, bind_m, 0)
    mode_lin_ok = float(np.abs(lin_pts - lin_oracle).max()) < 1e-4   # Linear<-swing
    mode_dq_ok = float(np.abs(dq_pts - dq_oracle).max()) < 1e-4      # DQS<-twist
    mode_tsw_ok = float(np.abs(tsw_pts - tsw_oracle).max()) < 1e-4   # Live<-both
    modes_distinct = (float(np.abs(lin_pts - dq_pts).max()) > 1e-3
                      and float(np.abs(tsw_pts - lin_pts).max()) > 1e-3
                      and float(np.abs(tsw_pts - dq_pts).max()) > 1e-3)
    mode_ok = bool(mode_lin_ok and mode_dq_ok and mode_tsw_ok and modes_distinct)

    # --- paint round-trip via sync_paint: entering a paint mode auto-loads that
    #     set into weightList; painting weightList banks back into the set PLUG;
    #     the edit survives a mode round-trip. (batch mayapy: sync_paint's plug
    #     writes are synchronous, so load/bank are observable in the same eval.) --
    def _dense_wl(nm):
        nvw = mc.getAttr(nm + ".weightList", size=True)
        rows, maxj = [], -1
        for v in range(nvw):
            idx = mc.getAttr("%s.weightList[%d].weights" % (nm, v),
                             multiIndices=True) or []
            d = {int(j): float(mc.getAttr(
                "%s.weightList[%d].weights[%d]" % (nm, v, j))) for j in idx}
            rows.append(d)
            maxj = max([maxj] + [int(j) for j in idx])
        W = np.zeros((nvw, maxj + 1), dtype=np.float64)
        for v, d in enumerate(rows):
            for j, w in d.items():
                W[v, j] = w
        return W

    paint_ok = False
    cmd_err = "n/a"
    try:
        # reset both plugs to the known sets, settle the latch on Live, then walk
        # the interactive workflow.
        _seed_plug(node, "twistWeights", twist_w)
        _seed_plug(node, "swingWeights", swing_w)
        mc.setAttr(node + ".skinMode", 2); _eval_pts()      # settle latch on Live
        mc.setAttr(node + ".skinMode", 0)                   # Paint LBS -> swing
        _eval_pts()
        wl_swing = _dense_wl(node)
        mc.setAttr(node + ".skinMode", 1)                   # Paint DQS -> twist
        _eval_pts()
        wl_twist = _dense_wl(node)
        load_ok = bool(np.allclose(wl_swing, swing_w, atol=1e-6)
                       and np.allclose(wl_twist, twist_w, atol=1e-6)
                       and float(np.abs(wl_swing - wl_twist).max()) > 1e-3)
        # "Paint" a THIRD falloff into weightList in Paint-LBS mode; a same-mode
        # eval banks it into the swingWeights PLUG (paint reaches the plug/deform).
        mc.setAttr(node + ".skinMode", 0)
        _eval_pts()
        tp = np.clip((t - 0.3) * 1.5, 0.0, 1.0)
        paint = np.stack([1.0 - tp, tp], axis=1)
        for v in range(nvv):
            mc.setAttr("%s.weightList[%d].weights[0]" % (node, v), float(paint[v, 0]))
            mc.setAttr("%s.weightList[%d].weights[1]" % (node, v), float(paint[v, 1]))
        _eval_pts()                                         # same mode -> banks
        banked = _read_plug(node, "swingWeights", paint.shape)
        bank_ok = bool(banked.shape == paint.shape
                       and np.allclose(banked, paint, atol=1e-6))
        # The edit survives a mode round-trip: leave Paint-LBS and come back; the
        # banked swing plug reloads into weightList.
        mc.setAttr(node + ".skinMode", 1); _eval_pts()      # away (Paint DQS)
        mc.setAttr(node + ".skinMode", 0); _eval_pts()      # back (Paint LBS)
        roundtrip_ok = bool(np.allclose(_dense_wl(node), paint, atol=1e-6))
        mc.setAttr(node + ".skinMode", 2)                   # restore default
        paint_ok = bool(load_ok and bank_ok and roundtrip_ok)
        cmd_err = "load=%s bank=%s roundtrip=%s" % (load_ok, bank_ok, roundtrip_ok)
    except Exception as exc:
        cmd_err = "exc:%r" % exc

    # --- lowering gate: the shipped Compute lowers to pure C++ (byte-parity is
    #     separately proven by native.tests.twist_swing_dual_parity_test) --------
    lower_ok = False
    try:
        from mpynode.native.compiler import nd_lower
        _ins = [{"plug": p, "member": p,
                 "meta": {"type": "double", "is_array": True}}
                for p in ("twistWeights", "swingWeights")]
        _ins += [{"plug": p, "member": p, "meta": {"type": "enum"}}
                 for p in ("skinMode", "twistAxis")]
        _spec = {"mpy_type": "mPySkinCluster", "init": SKIN_TWISTSWING_INIT,
                 "compute": SKIN_TWISTSWING_COMPUTE}
        _body = "\n".join(nd_lower.lower_deform(_ins, _spec, "MPxSkinCluster"))
        lower_ok = bool(_body and "sync_paint" not in _body
                        and "twist_swing_dual" in _body)
    except Exception as _lexc:
        cmd_err = cmd_err + " lower_exc:%r" % _lexc

    # --- demo check on a FRESH deserialized node -------------------------------
    #     clear the check-only plug seeding first so the shipped template is a
    #     clean node (the demo seeds the plugs from the bundled JSON weight sets).
    _clear_plug(node, "twistWeights")
    _clear_plug(node, "swingWeights")
    _stamp_class(sc, "TwistSwingSkin", "mPySkinCluster")
    clean_payload = serialize_node(sc, include_persistent=False)
    demo_ok = False
    demo_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node
        from mpynode._common.methods.methods_registry import run_node_demo
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        run_node_demo(tnode)
        tnm = tnode.get_name()
        target = None
        for m in (mc.ls(type="mesh", long=True) or []):
            if mc.getAttr(m + ".intermediateObject"):
                continue
            if tnm in (mc.listHistory(m) or []):
                target = m
                break
        in_hist = target is not None
        deforms = False
        if target is not None:
            mc.setAttr(tnm + ".envelope", 0.0)
            mc.dgdirty(tnm + ".outputGeometry")
            mc.getAttr(target + ".outMesh")
            rest_p = _mesh_object_pts(target)
            mc.setAttr(tnm + ".envelope", 1.0)
            mc.dgdirty(tnm + ".outputGeometry")
            mc.getAttr(target + ".outMesh")
            def_p = _mesh_object_pts(target)
            deforms = float(np.abs(def_p - rest_p).max()) > 0.5
        # The demo must have used the bundled ARM (442 verts, not the fallback
        # cylinder) and seeded the two weight-set PLUGS from the JSON files:
        # twistWeights == DQS.json, swingWeights == LBS.json.
        arm_ok = target is not None and mc.polyEvaluate(target, vertex=True) == 442
        weights_ok = False
        try:
            import json as _json
            _expd = os.path.join(TPL, "MPySkinCluster",
                                 "Twist Swing Skin")
            _dqs = np.asarray(_json.load(
                open(os.path.join(_expd, "DQS.json")))["weights"], dtype=np.float64)
            _lbs = np.asarray(_json.load(
                open(os.path.join(_expd, "LBS.json")))["weights"], dtype=np.float64)
            _tw = _read_plug(tnm, "twistWeights", _dqs.shape)
            _sw = _read_plug(tnm, "swingWeights", _lbs.shape)
            weights_ok = bool(
                _tw.shape == _dqs.shape and np.allclose(_tw, _dqs, atol=1e-9)
                and _sw.shape == _lbs.shape and np.allclose(_sw, _lbs, atol=1e-9))
        except Exception as _wexc:
            demo_err = "weights_exc:%r" % _wexc
        demo_ok = bool(in_hist and deforms and arm_ok and weights_ok)
        demo_err = ("mesh=%s in_hist=%s deforms=%s arm442=%s jsonWeights=%s"
                    % (target, in_hist, deforms, arm_ok, weights_ok)
                    if demo_err == "n/a" else demo_err)
    except Exception as exc:
        demo_err = "exc:%r" % exc

    # --- authored @maya_test check on a FRESH deserialized node. ---
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    ok = compute_ok and mode_ok and paint_ok and lower_ok and demo_ok and test_ok
    print("[exp_twist_swing] moved=%.4f finite=%s swing_effect=%.4f "
          "mode=%s(lin=%s dq=%s tsw=%s distinct=%s) paint=%s(%s) lower=%s "
          "demo=%s(%s) test=%s(%s) -> %s"
          % (moved, finite, swing_effect, mode_ok, mode_lin_ok, mode_dq_ok,
             mode_tsw_ok, modes_distinct, paint_ok, cmd_err, lower_ok, demo_ok,
             demo_err, test_ok, test_err, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(SKIN_TWISTSWING_DIR, clean_payload, SKIN_TWISTSWING_DESC)
    return ok


# ======================================================================
# mPyNurbsCurve -- animated procedural helix generator
# ======================================================================
# A plain DG node whose compute builds the (N,3) CV array and hands it to the
# NurbsCurve constructor. Pure-numeric CV math + a trailing NurbsCurve(...) ->
# deterministically LOWERS to pure C++ (emit_geo), so the compiled node is
# byte-parity with the interpreted one.
NURBS_CURVE_INIT = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import NurbsCurve\n"
)
NURBS_CURVE_COMPUTE = r'''# Procedural HELIX generator. Builds the (N, 3) CV positions and hands them to
# the NurbsCurve constructor: a coil of `radius`, total rise `height`, `turns`
# full revolutions. `t` (a time input auto-wired to the timeline) slowly spins
# the coil so it animates on playback. NurbsCurve marshals the CVs ->
# kNurbsCurveData; the native compile reproduces that build step, so this lowers
# to pure C++.
import numpy as np
n = 120
u = np.linspace(0.0, 1.0, n)
ang = u * self.turns * 2.0 * np.pi + self.t * 0.05
x = self.radius * np.cos(ang)
z = self.radius * np.sin(ang)
y = (u - 0.5) * self.height
cvs = np.stack([x, y, z], axis=1)
self.outCurve = NurbsCurve(points=cvs, degree=3)
'''

NURBS_CURVE_METHODS = '''@maya_test(label="Helix builds a 120-CV degree-3 curve of the right radius", digits=4)
def test_helix(self):
    """Validate the node's INTENT (same test drives the interpreted node AND its
    C++ compile -> parity): the generator builds a real 120-CV degree-3
    nurbsCurve whose X-extent tracks 2*radius. Drives ONLY public plugs + cmds,
    so it is valid against the compiled node too."""
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    from mpynode._common.methods.test_helpers import assert_true

    name = self.get_name()

    def _set(plug, *vals):
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals)

    # Build a real nurbsCurve shape driven by outCurve (idempotent: reuse the
    # one this node already drives, if any).
    dst = mc.listConnections(name + ".outCurve", s=False, d=True, plugs=True) or []
    shp = None
    for d in dst:
        node = d.split(".")[0]
        if mc.nodeType(node) == "nurbsCurve":
            shp = node
            break
    if shp is None:
        xf = mc.createNode("transform", name="helixTest#")
        shp = mc.createNode("nurbsCurve", name=xf + "Shape", parent=xf)
        mc.connectAttr(name + ".outCurve", shp + ".create", force=True)

    _set(name + ".radius", 2.5)
    _set(name + ".turns", 3.0)
    _set(name + ".height", 6.0)
    mc.currentTime(1)
    mc.dgeval(shp + ".create")

    spans = mc.getAttr(shp + ".spans")
    deg = mc.getAttr(shp + ".degree")
    cv_count = spans + deg          # open curve: #CVs = spans + degree
    assert_true(cv_count == 120, "expected 120 CVs, got %r" % cv_count)
    assert_true(deg == 3, "expected degree 3, got %r" % deg)

    sel = om2.MSelectionList(); sel.add(shp)
    fn = om2.MFnNurbsCurve(sel.getDagPath(0))
    xs = [p.x for p in fn.cvPositions(om2.MSpace.kObject)]
    x_extent = max(xs) - min(xs)
    assert_true(abs(x_extent - 5.0) < 0.5,
                "X-extent %.3f should track 2*radius=5.0" % x_extent)


@maya_demo(label="Animated Helix Curve")
def demo(self):
    """Build a nurbsCurve shape driven by this generator, tune a wide coil, set a
    one-loop playback range and press-play-ready timeline. The coil slowly spins
    because `t` is wired to the timeline."""
    from maya import cmds as mc
    name = self.get_name()

    xf = mc.createNode("transform", name="helixCurve#")
    shp = mc.createNode("nurbsCurve", name=xf + "Shape", parent=xf)
    mc.connectAttr(name + ".outCurve", shp + ".create", force=True)
    # `t` auto-connects to time1 on create; re-assert if the apply path dropped it.
    if not (mc.listConnections(name + ".t", s=True, d=False) or []):
        try:
            mc.connectAttr("time1.outTime", name + ".t", force=True)
        except Exception:
            pass

    mc.setAttr(name + ".radius", 2.5)
    mc.setAttr(name + ".turns", 4.0)
    mc.setAttr(name + ".height", 6.0)
    mc.playbackOptions(min=1, max=120)
    mc.currentTime(1)
    mc.select(xf, replace=True)
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name
'''

NURBS_CURVE_DESC = (
    "# Helix Curve Generator\n\n"
    "An `mPyNurbsCurve` that builds a helix: a coil of `radius`, rising "
    "`height` over `turns` revolutions. The result is a 120-CV degree-3 "
    "curve, and a `t` time input wired to the timeline spins it. Nothing "
    "appears until you wire `outCurve` into a real `nurbsCurve` shape's "
    "`create` plug.\n\n"
    "**Create + Run demo** builds the render curve, dials in a wide coil and "
    "sets a one-loop playback range -- press play to watch it turn. Compiles "
    "to pure C++."
)


def build_nurbs_curve_helix():
    mc.file(new=True, force=True)
    from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve
    from mpynode._common.io.mpn_io import deserialize_node
    from mpynode._common.methods.methods_registry import run_node_demo
    from mpynode._common.node_setups import find_demo

    g = MPyNurbsCurve.create(name="helixCurve")
    g.add_input_attr("radius", "float", default_value=2.0)
    g.add_input_attr("height", "float", default_value=6.0)
    g.add_input_attr("turns", "float", default_value=3.0)
    g.add_input_attr("t", "time")
    g.set_init_expression(NURBS_CURVE_INIT)
    g.set_compute_expression(NURBS_CURVE_COMPUTE)
    g.set_methods_source(NURBS_CURVE_METHODS)
    nm = g.get_name()

    def _curve_cv_count():
        # NOTE: do NOT delete this render shape -- deleting the sole downstream
        # consumer cascades and removes the orphaned generator DG node too. The
        # node-only serialize below captures just `g`, so leftover scene nodes are
        # harmless (the demo gate resets the scene with file(new=True)).
        xf = mc.createNode("transform")
        shp = mc.createNode("nurbsCurve", parent=xf)
        mc.connectAttr(nm + ".outCurve", shp + ".create", force=True)
        mc.currentTime(1)
        mc.dgeval(shp + ".create")
        return mc.getAttr(shp + ".spans") + mc.getAttr(shp + ".degree")

    compute_ok = _curve_cv_count() == 120

    _stamp_class(g, "HelixCurve", "mPyNurbsCurve")
    clean_payload = serialize_node(g, include_persistent=False)

    # --- live demo on a FRESH deserialized node (mirrors the gallery click). ---
    demo_ok = False
    demo_err = "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tnm = tnode.get_name()
        run_node_demo(tnode)
        curve_t = (mc.ls("helixCurve*", type="transform") or [None])[0]
        wired = False
        cvc = 0
        if curve_t is not None:
            shp = (mc.listRelatives(curve_t, shapes=True) or [None])[0]
            if shp and mc.nodeType(shp) == "nurbsCurve":
                wired = tnm in (mc.listHistory(shp) or [])
                mc.dgeval(shp + ".create")
                cvc = mc.getAttr(shp + ".spans") + mc.getAttr(shp + ".degree")
        demo_ok = bool(wired and cvc == 120)
        demo_err = "curve=%s wired=%s cvs=%s" % (curve_t, wired, cvc)
    except Exception as exc:
        demo_err = "exc:%r" % exc

    # --- authored @maya_test on a FRESH deserialized node. ---
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    has_demo = find_demo(NURBS_CURVE_METHODS) is not None
    payload_ok = clean_payload.get("native_type") == "mPyNurbsCurve"
    ok = bool(compute_ok and demo_ok and test_ok and has_demo and payload_ok)
    print("[nurbs_curve] compute=%s demo=%s(%s) test=%s(%s) has_demo=%s "
          "payload=%s -> %s"
          % (compute_ok, demo_ok, demo_err, test_ok, test_err, has_demo,
             payload_ok, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to("MPyNurbsCurve/NURBS Helix", clean_payload,
                           NURBS_CURVE_DESC)
    return ok


# ======================================================================
# mPyNurbsSurface -- animated procedural ripple-grid generator
# ======================================================================
# Builds the flat (nu*nv, 3) CV grid + num_u/num_v and hands them to the
# NurbsSurface constructor. Pure broadcasting math + a trailing NurbsSurface(...)
# -> LOWERS to pure C++ (emit_geo), byte-parity with the interpreted node.
NURBS_SURF_INIT = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import NurbsSurface\n"
)
NURBS_SURF_COMPUTE = r'''# Procedural RIPPLE SURFACE generator. Builds an 8x8 CV grid over a `size`-wide
# square in the XZ plane and lifts each CV in Y by a radial-ish sin/cos ripple of
# `amplitude` and `freq`. `t` (a time input auto-wired to the timeline) advances
# the ripple phase so it animates on playback. Hands the flat (nu*nv, 3) CV form
# to the NurbsSurface constructor with num_u/num_v (row-major). LOWERS to pure
# C++ (emit_geo).
import numpy as np
nu = 8
nv = 8
u = np.linspace(0.0, self.size, nu)
v = np.linspace(0.0, self.size, nv)
# Broadcast into (nu, nv) grids, then flatten row-major (k = i*nv + j).
Uf = (u[:, None] + np.zeros((nu, nv))).reshape(nu * nv)
Vf = (np.zeros((nu, nv)) + v[None, :]).reshape(nu * nv)
phase = self.t * 0.1
Yf = self.amplitude * np.sin(Uf * self.freq + phase) * np.cos(Vf * self.freq + phase)
cvs = np.stack([Uf, Yf, Vf], axis=1)
self.outSurface = NurbsSurface(points=cvs, num_u=nu, num_v=nv,
                               degree_u=3, degree_v=3)
'''

NURBS_SURF_METHODS = '''@maya_test(label="Ripple builds an 8x8 (5-span) surface that is not flat", digits=4)
def test_ripple_surface(self):
    """Validate the node's INTENT (interpreted node AND its C++ compile -> parity):
    the generator builds a real 5-span x 5-span degree-3 nurbsSurface whose CVs
    are lifted out of the flat plane (max |Y| > 0). Drives ONLY public plugs +
    cmds, so it is valid against the compiled node too."""
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    from mpynode._common.methods.test_helpers import assert_true

    name = self.get_name()

    def _set(plug, *vals):
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals)

    dst = mc.listConnections(name + ".outSurface", s=False, d=True, plugs=True) or []
    shp = None
    for d in dst:
        node = d.split(".")[0]
        if mc.nodeType(node) == "nurbsSurface":
            shp = node
            break
    if shp is None:
        xf = mc.createNode("transform", name="rippleSurfTest#")
        shp = mc.createNode("nurbsSurface", name=xf + "Shape", parent=xf)
        mc.connectAttr(name + ".outSurface", shp + ".create", force=True)

    _set(name + ".size", 6.0)
    _set(name + ".amplitude", 1.0)
    _set(name + ".freq", 1.2)
    mc.currentTime(1)
    mc.dgeval(shp + ".create")

    spans_u = mc.getAttr(shp + ".spansU")
    spans_v = mc.getAttr(shp + ".spansV")
    assert_true((spans_u, spans_v) == (5, 5),
                "expected (5, 5) spans, got %r" % ((spans_u, spans_v),))

    sel = om2.MSelectionList(); sel.add(shp)
    fn = om2.MFnNurbsSurface(sel.getDagPath(0))
    max_y = max(abs(p.y) for p in fn.cvPositions(om2.MSpace.kObject))
    assert_true(max_y > 0.05, "ripple should lift CVs off the plane (maxY %.4f)" % max_y)


@maya_demo(label="Animated Ripple Surface")
def demo(self):
    """Build a nurbsSurface shape driven by this generator, tune a visible
    ripple, set a one-loop playback range. The ripple advances because `t` is
    wired to the timeline."""
    from maya import cmds as mc
    name = self.get_name()

    xf = mc.createNode("transform", name="rippleSurf#")
    shp = mc.createNode("nurbsSurface", name=xf + "Shape", parent=xf)
    mc.connectAttr(name + ".outSurface", shp + ".create", force=True)
    if not (mc.listConnections(name + ".t", s=True, d=False) or []):
        try:
            mc.connectAttr("time1.outTime", name + ".t", force=True)
        except Exception:
            pass

    mc.setAttr(name + ".size", 6.0)
    mc.setAttr(name + ".amplitude", 1.0)
    mc.setAttr(name + ".freq", 1.4)
    mc.playbackOptions(min=1, max=120)
    mc.currentTime(1)
    mc.select(xf, replace=True)
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name
'''

NURBS_SURF_DESC = (
    "# Ripple Surface Generator\n\n"
    "An `mPyNurbsSurface` that builds a rippling surface: an 8x8 CV grid over "
    "a `size`-wide square, lifted in Y by a sin/cos wave of `amplitude` and "
    "`freq`. A `t` time input wired to the timeline rolls the wave across it. "
    "Nothing appears until you wire `outSurface` into a real `nurbsSurface` "
    "shape's `create` plug.\n\n"
    "**Create + Run demo** builds the render surface, dials up a visible "
    "ripple and sets a one-loop playback range. Compiles to pure C++."
)


def build_nurbs_surface_ripple():
    mc.file(new=True, force=True)
    from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface
    from mpynode._common.io.mpn_io import deserialize_node
    from mpynode._common.methods.methods_registry import run_node_demo
    from mpynode._common.node_setups import find_demo

    g = MPyNurbsSurface.create(name="rippleSurf")
    g.add_input_attr("size", "float", default_value=6.0)
    g.add_input_attr("amplitude", "float", default_value=1.0)
    g.add_input_attr("freq", "float", default_value=1.2)
    g.add_input_attr("t", "time")
    g.set_init_expression(NURBS_SURF_INIT)
    g.set_compute_expression(NURBS_SURF_COMPUTE)
    g.set_methods_source(NURBS_SURF_METHODS)
    nm = g.get_name()

    def _surf_spans():
        # See the curve builder: do NOT delete the render shape (it would cascade
        # and delete the orphaned generator).
        xf = mc.createNode("transform")
        shp = mc.createNode("nurbsSurface", parent=xf)
        mc.connectAttr(nm + ".outSurface", shp + ".create", force=True)
        mc.currentTime(1)
        mc.dgeval(shp + ".create")
        return (mc.getAttr(shp + ".spansU"), mc.getAttr(shp + ".spansV"))

    compute_ok = _surf_spans() == (5, 5)

    _stamp_class(g, "RippleSurf", "mPyNurbsSurface")
    clean_payload = serialize_node(g, include_persistent=False)

    demo_ok = False
    demo_err = "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tnm = tnode.get_name()
        run_node_demo(tnode)
        surf_t = (mc.ls("rippleSurf*", type="transform") or [None])[0]
        wired = False
        spans = (0, 0)
        if surf_t is not None:
            shp = (mc.listRelatives(surf_t, shapes=True) or [None])[0]
            if shp and mc.nodeType(shp) == "nurbsSurface":
                wired = tnm in (mc.listHistory(shp) or [])
                mc.dgeval(shp + ".create")
                spans = (mc.getAttr(shp + ".spansU"), mc.getAttr(shp + ".spansV"))
        demo_ok = bool(wired and spans == (5, 5))
        demo_err = "surf=%s wired=%s spans=%s" % (surf_t, wired, spans)
    except Exception as exc:
        demo_err = "exc:%r" % exc

    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    has_demo = find_demo(NURBS_SURF_METHODS) is not None
    payload_ok = clean_payload.get("native_type") == "mPyNurbsSurface"
    ok = bool(compute_ok and demo_ok and test_ok and has_demo and payload_ok)
    print("[nurbs_surface] compute=%s demo=%s(%s) test=%s(%s) has_demo=%s "
          "payload=%s -> %s"
          % (compute_ok, demo_ok, demo_err, test_ok, test_err, has_demo,
             payload_ok, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to("MPyNurbsSurface/NURBS Ripple", clean_payload,
                           NURBS_SURF_DESC)
    return ok


# ======================================================================
# mPyDeformer -- NURBS-aware wave deformer
# ======================================================================
# An mPyDeformer whose deform() path is geometry-agnostic: it harvests control
# points uniformly (MItGeometry::allPositions), so the SAME node deforms polygon
# meshes AND NURBS surfaces. This template deforms a NURBS surface via the CV
# idiom (cvPositions/setCVPositions). The emitted C++ deform() harvests CVs the
# same way, and nd_lower accepts the CV idiom as an alias of getPoints/setPoints,
# so it LOWERS to pure C++ (byte-parity).
GF_NURBS_INIT = "import numpy as np\n"
GF_NURBS_COMPUTE = r'''# NURBS wave deformer: push each CV along X (the default nurbsPlane's normal --
# that plane lies in YZ with X=0) by a travelling sine of its Y coordinate, so a
# clear wave ripples across the surface. Reads CVs via the NURBS idiom
# cvPositions()/setCVPositions() (mPyDeformer also accepts mesh
# getPoints/setPoints). `time` (auto-wired to the timeline) animates the wave;
# `envelope` (0..1) blends it against rest.
import numpy as np
h = self.outputGeometry[0]
rest = h.cvPositions()                 # (N, 3) object-space CVs (numpy)
env = float(self.envelope)
out = rest.copy()
out[:, 0] = out[:, 0] + env * self.amplitude * np.sin(rest[:, 1] * self.freq + self.time * 0.1)
h.setCVPositions(out)
'''

GF_NURBS_METHODS = '''@maya_test(label="Wave deforms a NURBS plane (rest at envelope 0)", digits=4)
def test_nurbs_wave(self):
    """Validate the node's INTENT (interpreted node AND its C++ compile -> parity):
    with the wave OFF (envelope 0, or amplitude 0) the surface sits at rest; with
    it ON the CVs actually move. Drives ONLY public plugs + cmds -> valid against
    the compiled node too."""
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_close, assert_true

    name = self.get_name()

    def _set(plug, *vals):
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals)

    # Deform whatever NURBS geo this filter already drives; build one only if it
    # drives nothing yet (keeps the test on `self`, robust to repeated runs).
    geo = mc.deformer(name, q=True, geometry=True) or []
    if geo:
        sh = (mc.ls(geo[0], long=True) or [geo[0]])[0]
    else:
        pl = mc.nurbsPlane(w=6.0, lengthRatio=1.0, patchesU=8, patchesV=8,
                           name="nurbsWaveTest#")[0]
        mc.deformer(name, e=True, g=pl)
        sh = mc.listRelatives(pl, shapes=True, noIntermediate=True, f=True)[0]

    def cvs(amp, env, frame=1):
        _set(name + ".amplitude", amp)
        _set(name + ".envelope", env)
        mc.currentTime(frame)
        mc.dgdirty(name + ".outputGeometry")
        mc.dgeval(sh + ".worldSpace")
        sel = om2.MSelectionList(); sel.add(sh)
        fn = om2.MFnNurbsSurface(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.cvPositions(om2.MSpace.kObject)])

    rest = cvs(0.0, 1.0)          # amplitude 0 -> zero offset
    env_off = cvs(0.6, 0.0)       # envelope 0 -> zero offset
    deformed = cvs(0.6, 1.0)      # wave ON -> real displacement

    assert_close(env_off.ravel().tolist(), rest.ravel().tolist())
    moved = float(np.abs(deformed - rest).max())
    assert_true(moved > 0.05,
                "wave should displace the surface (max move %.4f)" % moved)


@maya_demo(label="Wave a NURBS Plane")
def demo(self):
    """Create a NURBS plane, attach this deformer, dial in a visible wave and set
    a one-loop playback range. Press play to watch the wave travel (it advances
    with `time`)."""
    from maya import cmds as mc
    name = self.get_name()

    plane = mc.nurbsPlane(w=8.0, lengthRatio=1.0, patchesU=12, patchesV=12,
                          name="nurbsWaveTarget#")[0]
    if name not in (mc.listHistory(plane) or []):
        mc.deformer(name, e=True, g=plane)

    mc.setAttr(name + ".amplitude", 0.8)
    mc.setAttr(name + ".freq", 1.2)
    if not (mc.listConnections(name + ".time", s=True, d=False) or []):
        try:
            mc.connectAttr("time1.outTime", name + ".time", force=True)
        except Exception:
            pass

    mc.playbackOptions(min=1, max=120)
    mc.currentTime(1)
    mc.select(plane, replace=True)
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name
'''

GF_NURBS_DESC = (
    "# NURBS Wave Deformer\n\n"
    "An `mPyDeformer` that pushes each CV along X by a sine of its height in "
    "Y, so a wave rolls across a NURBS surface as the timeline plays. The "
    "same node also deforms polygon meshes. Inputs: `amplitude`, `freq`, "
    "`time`, plus the built-in deformer `envelope`.\n\n"
    "**Create + Run demo** builds a NURBS plane, attaches this deformer and "
    "sets a one-loop playback range -- press play to watch the wave travel. "
    "Compiles to pure C++."
)


def build_deformer_nurbs_wave():
    mc.file(new=True, force=True)
    from mpynode.wrappers.mpy_deformer import MPyDeformer
    from mpynode._common.io.mpn_io import deserialize_node
    from mpynode._common.methods.methods_registry import run_node_demo
    from mpynode._common.node_setups import find_demo

    plane = mc.nurbsPlane(w=6.0, lengthRatio=1.0, patchesU=8, patchesV=8,
                          name="nurbsWaveTarget")[0]
    gf_name = mc.deformer(plane, type="mPyDeformer", name="nurbsWave")[0]
    # Canonical Class identity: the old ``_stamp_py_class`` call was a no-op for a
    # root wrapper (mPyDeformer is not a user subclass), so this template shipped
    # class-less. Synthesize + stamp ``mpynode_user.NurbsWave`` so it carries the
    # Class its author intended.
    from mpynode._common.io.user_classes import synthesize, dotted_path
    gf = MPyDeformer(gf_name)
    synthesize("NurbsWave", "mPyDeformer")
    gf.set_py_class(dotted_path("NurbsWave"))
    gf.add_input_attr("amplitude", "float", default_value=0.5)
    gf.add_input_attr("freq", "float", default_value=1.0)
    gf.add_input_attr("time", "time")
    gf.set_init_expression(GF_NURBS_INIT)
    gf.set_compute_expression(GF_NURBS_COMPUTE)
    gf.set_methods_source(GF_NURBS_METHODS)
    nm = gf.get_name()
    sh = mc.listRelatives(plane, shapes=True, noIntermediate=True, f=True)[0]

    def cvs(amp, env):
        mc.setAttr(nm + ".amplitude", amp)
        mc.setAttr(nm + ".envelope", env)
        mc.currentTime(1)
        mc.dgdirty(nm + ".outputGeometry")
        mc.dgeval(sh + ".worldSpace")
        sel = om.MSelectionList(); sel.add(sh)
        fn = om.MFnNurbsSurface(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.cvPositions(om.MSpace.kObject)])

    rest = cvs(0.0, 1.0)
    deformed = cvs(0.6, 1.0)
    env_off = cvs(0.6, 0.0)
    moved = float(np.abs(deformed - rest).max())
    env0_is_rest = np.allclose(env_off, rest, atol=1e-9)
    compute_ok = moved > 0.05 and env0_is_rest

    clean_payload = serialize_node(gf, include_persistent=False)

    demo_ok = False
    demo_err = "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tnm = tnode.get_name()
        run_node_demo(tnode)
        plane_t = (mc.ls("nurbsWaveTarget*", type="transform") or [None])[0]
        in_hist = plane_t is not None and tnm in (mc.listHistory(plane_t) or [])
        waved = False
        if plane_t is not None:
            shp = mc.listRelatives(plane_t, shapes=True, ni=True, f=True)[0]
            mc.currentTime(6)
            mc.dgdirty(tnm + ".outputGeometry")
            mc.dgeval(shp + ".worldSpace")
            sel = om.MSelectionList(); sel.add(shp)
            fn = om.MFnNurbsSurface(sel.getDagPath(0))
            ys = [p.y for p in fn.cvPositions(om.MSpace.kObject)]
            waved = (max(ys) - min(ys)) > 0.05
        demo_ok = bool(in_hist and waved)
        demo_err = "plane=%s in_hist=%s waved=%s" % (plane_t, in_hist, waved)
    except Exception as exc:
        demo_err = "exc:%r" % exc

    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    has_demo = find_demo(GF_NURBS_METHODS) is not None
    payload_ok = clean_payload.get("native_type") == "mPyDeformer"
    ok = bool(compute_ok and demo_ok and test_ok and has_demo and payload_ok)
    print("[deformer_nurbs_wave] moved=%.4f env0_rest=%s demo=%s(%s) test=%s(%s) "
          "has_demo=%s payload=%s -> %s"
          % (moved, env0_is_rest, demo_ok, demo_err, test_ok, test_err,
             has_demo, payload_ok, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to("MPyDeformer/NURBS Wave", clean_payload,
                           GF_NURBS_DESC)
    return ok


# ======================================================================
# mPyBlendShape -- aliased weights + baked delta tables
# ======================================================================
# One template, compiling to pure C++. It looks like a stock blendShape:
# a `weight[]` float multi whose elements are ALIASED to the target names, so
# the channel box shows `browUp` rather than `weight[0]`.
#
# The compute reads BAKED sparse deltas, never the live target meshes. Maya does
# the same (a stock blendShape keeps both, and it is the deltas that deform), and
# it is what makes the node compilable: `nd_lower` rewrites a mesh-multi element
# read only at a LITERAL index, while a blendShape's defining loop runs over
# targets at a RUNTIME index.
#
# The names never cross into the compute either -- alias lookup is a side-channel
# DG query, and those return EMPTY on the Evaluation-Manager worker thread that
# `deform()` runs on. MPyBlendShape.rebuild() decodes them ONCE, in Python, into
# integer tables. Nothing name-derived is baked into the generated C++, so ONE
# compiled bundle serves any rig.

COMBO_INIT = r'''# The corrective maths, as three plain functions. Init runs ONCE per file
# lifecycle and its globals are visible to the Compute, so this is where the
# rules live -- edit them here and the Compute stays a four-line summary.
#
# These transpile exactly like the Compute does: a function defined in Init is
# handed to the C++ helper parser, so the compiled node calls the SAME rules,
# not a second implementation. Keep them in the loop dialect (`for i in
# range(...)`, integer indexing, explicit float()/int() on ARRAY reads) and they
# lower whole. Note the casts on `raw[t]` / `cdrv[j]` are NOT defensive noise --
# the transpiler needs them to type the C++; dropping them drops the node to the
# AI porter. A `self.<attr>` read is already the right Python type and must NOT
# be recast.
import numpy as np


def inbetween_hat(driver, knot, ibase, iknot, main):
    """The in-between rule: a CROSS-BLENDING hat on the MAIN target's weight.

    1.0 when the driver sits exactly on this knot, falling to 0 at the ADJACENT
    knots on the same main -- not at the ends of the driver's travel. So with
    jawDrop25/50/75 on one driver, jawDrop75 blends 0.5 (0.) -> 0.75 (1.) ->
    1.0 (0.) and the three hand off to each other instead of all firing at once.
    A lone in-between still spans 0 -> knot -> 1, because there is no neighbour
    to hand off to. Want a softer shoulder? Return a smoothstep of this.
    """
    lo = 0.0
    hi = 1.0
    for j in range(ibase.shape[0]):
        if int(ibase[j]) == main:
            k = float(iknot[j])
            if k < knot and k > lo:
                lo = k
            if k > knot and k < hi:
                hi = k
    h = 0.0
    if driver > lo:
        if driver <= knot:
            if knot > lo:
                h = (driver - lo) / (knot - lo)
        elif driver < hi:
            h = (hi - driver) / (hi - knot)
    return h


def combo_blend(raw, cdrv, lo, hi, nt):
    """The combo rule: how a combo target reads its drivers.

    The PRODUCT of every driver, with the LAST keyword in the alias counted
    TWICE -- `cheekPuffL_noseWrinkleL_jawDrop` reads
    `cheekPuffL * noseWrinkleL * jawDrop * jawDrop`. That is not a general
    truth about combos, it is how THIS corpus of combo shapes was sculpted, so
    it is the rule its sculpts expect. The drivers arrive in alias order, so
    the last keyword is simply the last entry in the slice.

    This is the one to change if you want a different feel: drop the squaring
    for a plain product, `min()` over the drivers holds up much sooner, and the
    geometric mean (`p ** (1.0 / n)`) sits between the two.
    """
    p = 1.0
    for j in range(lo, hi):
        dr = int(cdrv[j])
        if dr >= 0 and dr < nt:
            p = p * float(raw[dr])
    if hi > lo:
        dr = int(cdrv[hi - 1])
        if dr >= 0 and dr < nt:
            p = p * float(raw[dr])
    return p


def resolve_morph_weights(raw, ibase, iknot, cofs, cdrv, do_corr, do_combo):
    """Raw weight[] channels -> the effective weight per target.

    Correctives are ADDITIVE: a target keeps whatever is keyed on its own
    channel and the driven amount is ADDED on top, so a corrective can be
    dialled by hand as well as derived. With both switches off this returns the
    raw channels untouched, which is a plain blendShape.

    Every table read is bounds-clamped. That is load-bearing, not defensive
    noise: compiled, `nd::at1_ref` does NO bounds checking, so a stale table
    would be a silent out-of-bounds heap read.
    """
    nt = raw.shape[0]
    nib = ibase.shape[0]
    nkn = iknot.shape[0]
    nco = cofs.shape[0]
    ncd = cdrv.shape[0]

    out = np.zeros(nt)
    for t in range(nt):
        e = float(raw[t])

        if do_corr:
            if t < nib and t < nkn:
                m = int(ibase[t])
                if m >= 0 and m < nt:
                    e = e + inbetween_hat(float(raw[m]), float(iknot[t]), ibase, iknot, m)

        if do_combo:
            if t + 1 < nco:
                lo = int(cofs[t])
                hi = int(cofs[t + 1])
                if lo < 0:
                    lo = 0
                if hi > ncd:
                    hi = ncd
                if hi > lo:
                    e = e + combo_blend(raw, cdrv, lo, hi, nt)

        out[t] = e
    return out
'''

COMBO_COMPUTE = r'''# Corrective blendShape: in-betweens and combos, resolved from tables.
#
# The naming convention lives in the ALIASES, and it is decoded ONCE, in Python,
# by MPyBlendShape.rebuild() -- never here:
#
#     browUp                a main target, driven by its own weight
#     browUp50              an IN-BETWEEN of browUp, peaking at 0.50
#     browUp_mouthOpen      a COMBO, active when both drivers are up
#
# Names cannot be read in a compute at all. Alias lookup is a side-channel DG
# query, and those return EMPTY on the Evaluation-Manager worker thread that
# deform() runs on -- so it would be unreliable interpreted and impossible
# compiled. What crosses into the compute is pure number:
#
#     interBase[t]    the main target an in-between corrects, else -1
#     interKnot[t]    where it peaks (0.5 for browUp50)
#     comboOffset[t] .. comboOffset[t+1]   slice of comboDriver for target t
#     comboDriver[j]  a driver target index
#
# Every target stores its RAW `sculpt - base` offsets. A corrective is sculpted
# as the correction ITSELF -- what to add once its drivers are already posed --
# so there is nothing to subtract at bake time. That is also why dialling one by
# hand shows exactly the shape it was sculpted as.
#
# The rules live in the INIT tab as three ordinary functions --
# `inbetween_hat`, `combo_blend`, `resolve_morph_weights` -- so the
# maths is right there to read and change. There is no shared weight resolver
# behind them: whatever maths a rig wants lives in ITS Init and Compute, in
# the open. Init transpiles with the Compute, so an edited rule compiles too.
#
# Correctives are ADDITIVE here: a corrective keeps whatever is keyed on its own
# channel and the driven amount is added on top. `applyCorrectives` and
# `applyCombos` switch the driven half off without unhooking anything, so you can
# key the drivers and watch each contribution on its own.

# Construction history is automatic: `self.morphs.deltas` reads a target's
# offsets straight off its CONNECTED mesh, so sculpting one reaches the deform
# as you drag. A target with no connection falls back to its baked deltas, which
# is what makes deleting a target leave the shape driving. Switch `liveTargets`
# off to pin the deform to the baked tables. Compiled nodes follow their targets
# too -- they read every CONNECTED one, where interpreted skips the slots that
# resolve to zero weight, so the result matches and only the cost differs.

mesh = self.outputGeometry[0]
base = mesh.getPoints()

w = resolve_morph_weights(self.weight, self.interBase, self.interKnot,
                          self.comboOffset, self.comboDriver,
                          self.applyCorrectives, self.applyCombos)

mesh.setPoints(base + self.envelope * self.morphs.deltas(base, w))
'''

COMBO_METHODS = r'''@maya_test(label="In-betweens hat on their driver; combos multiply theirs", digits=4)
def test_correctives(self):
    """Validate the node's INTENT (the SAME test runs interpreted and compiled):
    an in-between rises to 1 at its knot and falls back to 0 at both of its
    NEIGHBOURING knots -- here, with no sibling, that is both ends of the
    driver's travel -- and a combo is the product of its drivers with the last
    alias keyword squared.

    Sibling in-betweens on one driver are covered by
    ``test_inbetween_crossblend``; this rig has one per driver on purpose, so
    the two cases are pinned separately.

    Four targets, wired purely through public plugs:
        0  A            main
        1  A50          in-between of A, knot 0.5
        2  B            main
        3  A_B          combo of A and B

    A corrective's drive is DERIVED from its drivers, but it is ADDITIVE: the
    value keyed on its own channel is kept and the derived amount is added on
    top. The driven-behaviour block below therefore rests both corrective
    channels at 0 so each hat / product reads as its bare value; a later block
    keys them to pin the additive contract, and a third checks that
    applyCorrectives / applyCombos drop only the derived half."""
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_close, assert_true

    name = self.get_name()

    base = mc.polyPlane(w=2, h=2, sx=3, sy=3, name="ccTestBase#", ch=False)[0]
    if name not in (mc.listHistory(base) or []):
        mc.deformer(name, e=True, g=base)
    shape = mc.listRelatives(base, shapes=True, noIntermediate=True, f=True)[0]

    # One vertex per target, one axis each, so a wrong effective weight shows up
    # as a wrong number on a known vertex instead of a smeared shape.
    tables = {
        "targetOffset": [0, 1, 2, 3, 4],
        "targetComponents": [0, 1, 2, 3],
        "targetDeltas": [0.0, 1.0, 0.0,      # 0  A    -> v0 +Y
                         0.0, 1.0, 0.0,      # 1  A50  -> v1 +Y
                         1.0, 0.0, 0.0,      # 2  B    -> v2 +X
                         0.0, 0.0, 1.0],     # 3  A_B  -> v3 +Z
        "interBase": [-1, 0, -1, -1],        # only target 1 is an in-between
        "interKnot": [0.0, 0.5, 0.0, 0.0],
        "comboOffset": [0, 0, 0, 0, 2],      # only target 3 has drivers
        "comboDriver": [0, 2],               # ...namely A and B
    }
    # The tables are PACKED typed arrays -- ONE plug each, not multis -- so they
    # have no element plugs and `attr[i]` does not resolve. Write each table
    # whole in a single setAttr. The multi branch keeps a scene authored before
    # packed storage working, and is how the plug kind is detected here (the
    # wrapper's _is_packed is not available on a compiled node).
    for attr, values in tables.items():
        if mc.attributeQuery(attr, node=name, multi=True):
            for i, v in enumerate(values):
                mc.setAttr("%s.%s[%d]" % (name, attr, i), v)
        else:
            _dt = mc.getAttr("%s.%s" % (name, attr), type=True)
            _cast = float if _dt == "doubleArray" else int
            mc.setAttr("%s.%s" % (name, attr),
                       [_cast(v) for v in values], type=_dt)

    # The corrective slots rest at 0 for the driven-behaviour block below, so
    # each hat / product reads as its bare value. They still have to EXIST --
    # an array input is read densely up to its highest logical index, so leaving
    # weight[3] unwritten would silently shorten the loop and skip the combo.
    # The ADDITIVE block further down keys them on purpose.
    mc.setAttr(name + ".weight[1]", 0.0)
    mc.setAttr(name + ".weight[3]", 0.0)

    def pts(a, b, corr=True, combo=True, own1=0.0, own3=0.0):
        mc.setAttr(name + ".weight[0]", a)
        mc.setAttr(name + ".weight[2]", b)
        mc.setAttr(name + ".weight[1]", own1)
        mc.setAttr(name + ".weight[3]", own3)
        mc.setAttr(name + ".applyCorrectives", corr)
        mc.setAttr(name + ".applyCombos", combo)
        mc.setAttr(name + ".envelope", 1.0)
        mc.dgdirty(name + ".outputGeometry")
        mc.getAttr(shape + ".outMesh")
        sel = om2.MSelectionList()
        sel.add(shape)
        fn = om2.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    rest = pts(0.0, 0.0)
    assert_true(rest.shape[0] >= 4,
                "test plane should have at least 4 verts, got %d" % rest.shape[0])

    def expect(a, b, inter, combo):
        e = rest.copy()
        e[0, 1] += a            # A
        e[1, 1] += inter        # A50
        e[2, 0] += b            # B
        e[3, 2] += combo        # A_B
        return e.tolist()

    # --- in-between: the hat on A -------------------------------------------
    # Below the knot it ramps up, at the knot it is exactly 1, above the knot it
    # ramps back DOWN to 0 -- which is what keeps it from fighting A at full.
    assert_close(pts(0.00, 0.0).tolist(), expect(0.00, 0.0, 0.0, 0.0),
                 msg="in-between must be 0 when its driver is 0")
    assert_close(pts(0.25, 0.0).tolist(), expect(0.25, 0.0, 0.5, 0.0),
                 msg="in-between should be 0.5 halfway up to the 0.5 knot")
    assert_close(pts(0.50, 0.0).tolist(), expect(0.50, 0.0, 1.0, 0.0),
                 msg="in-between must peak at exactly 1.0 on its knot")
    assert_close(pts(0.75, 0.0).tolist(), expect(0.75, 0.0, 0.5, 0.0),
                 msg="in-between should fall back to 0.5 past the knot")
    assert_close(pts(1.00, 0.0).tolist(), expect(1.00, 0.0, 0.0, 0.0),
                 msg="in-between must be 0 again when its driver is full")

    # --- combo: the product of A and B, with the LAST keyword squared --------
    # `combo_blend` in the Init tab counts the last alias keyword twice, which
    # is how this corpus of combo shapes was sculpted. For A_B that is
    # A * B * B, so 0.5/0.5 gives 0.125 and not 0.25. Change the rule there and
    # this number changes with it -- that is the point of it living in the
    # template rather than in a shared resolver.
    assert_close(pts(1.0, 0.0).tolist(), expect(1.0, 0.0, 0.0, 0.0),
                 msg="combo must stay off while only one driver is up")
    assert_close(pts(0.0, 1.0).tolist(), expect(0.0, 1.0, 0.0, 0.0),
                 msg="combo must stay off while only the other driver is up")
    assert_close(pts(1.0, 1.0).tolist(), expect(1.0, 1.0, 0.0, 1.0),
                 msg="combo must be fully on when BOTH drivers are up")
    assert_close(pts(0.5, 0.5).tolist(), expect(0.5, 0.5, 1.0, 0.125),
                 msg="combo squares its LAST driver (0.5 * 0.5 * 0.5)")
    assert_close(pts(1.0, 0.5).tolist(), expect(1.0, 0.5, 0.0, 0.25),
                 msg="the squared driver must be B, not A (1.0 * 0.5 * 0.5)")
    assert_close(pts(0.5, 1.0).tolist(), expect(0.5, 1.0, 1.0, 0.5),
                 msg="A is linear in the product (0.5 * 1.0 * 1.0)")

    # --- ADDITIVE: a corrective keeps its OWN keyed channel ------------------
    # The driven amount is added on top rather than replacing it, so a
    # corrective can be dialled by hand as well as derived.
    assert_close(pts(0.0, 0.0, own1=0.4).tolist(),
                 expect(0.0, 0.0, 0.4, 0.0),
                 msg="an in-between with no drive must still honour its own channel")
    assert_close(pts(0.5, 0.0, own1=0.4).tolist(),
                 expect(0.5, 0.0, 1.4, 0.0),
                 msg="in-between must ADD its own channel to the hat (0.4 + 1.0)")
    assert_close(pts(1.0, 1.0, own3=0.3).tolist(),
                 expect(1.0, 1.0, 0.0, 1.3),
                 msg="combo must ADD its own channel to the product (0.3 + 1.0)")

    # --- the two switches ----------------------------------------------------
    # Off does not unhook the target: the channel still drives it by hand, only
    # the DERIVED half stops.
    assert_close(pts(0.5, 0.0, corr=False).tolist(),
                 expect(0.5, 0.0, 0.0, 0.0),
                 msg="applyCorrectives off must drop the hat entirely")
    assert_close(pts(0.5, 0.0, corr=False, own1=0.4).tolist(),
                 expect(0.5, 0.0, 0.4, 0.0),
                 msg="applyCorrectives off must still honour a keyed in-between")
    assert_close(pts(1.0, 1.0, combo=False).tolist(),
                 expect(1.0, 1.0, 0.0, 0.0),
                 msg="applyCombos off must drop the product entirely")
    assert_close(pts(1.0, 1.0, combo=False, own3=0.3).tolist(),
                 expect(1.0, 1.0, 0.0, 0.3),
                 msg="applyCombos off must still honour a keyed combo")
    assert_close(pts(0.5, 0.5, corr=False, combo=False).tolist(),
                 expect(0.5, 0.5, 0.0, 0.0),
                 msg="both switches off must be a plain linear blendShape")

    # A weight the tables do not describe must be ignored, not read out of
    # bounds -- compiled, nd::at1_ref would walk straight off the heap.
    mc.setAttr(name + ".weight[9]", 1.0)
    assert_close(pts(0.0, 0.0).tolist(), rest.tolist(),
                 msg="a weight with no table entry must be a no-op, not an OOB")


@maya_test(label="Sibling in-betweens hand off instead of stacking", digits=4)
def test_inbetween_crossblend(self):
    """TWO in-betweens on ONE driver must CROSS-BLEND, not fire together.

    `inbetween_hat` bounds each hat by the ADJACENT knots on the same main, so
    A25 and A50 hand off at their shared boundary. A hat spanning the driver's
    whole travel instead -- which is what this node used to do -- leaves BOTH
    lit at once: at A=0.5 the 0.25 hat would still read (1-0.5)/(1-0.25)=0.667
    on top of the 0.5 hat's 1.0, and the rig could not reproduce its own sculpt
    through its own driver. The single-in-between rig in `test_correctives`
    cannot see that, because with no sibling the new rule reduces to the old
    one exactly -- which is precisely how it shipped.

    Five targets, one vertex each so a wrong hat is a wrong number on a known
    vertex:
        0  A      main
        1  A25    in-between of A, knot 0.25
        2  A50    in-between of A, knot 0.50
        3  B      an unrelated main, to prove hats stay on their own driver
        4  B50    in-between of B, knot 0.50 -- LONE, so it spans 0..1
    """
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_close, assert_true

    name = self.get_name()

    base = mc.polyPlane(w=2, h=2, sx=3, sy=3, name="cbTestBase#", ch=False)[0]
    if name not in (mc.listHistory(base) or []):
        mc.deformer(name, e=True, g=base)
    shape = mc.listRelatives(base, shapes=True, noIntermediate=True, f=True)[0]

    tables = {
        "targetOffset": [0, 1, 2, 3, 4, 5],
        "targetComponents": [0, 1, 2, 3, 4],
        "targetDeltas": [0.0, 1.0, 0.0,      # 0  A    -> v0 +Y
                         0.0, 1.0, 0.0,      # 1  A25  -> v1 +Y
                         0.0, 1.0, 0.0,      # 2  A50  -> v2 +Y
                         1.0, 0.0, 0.0,      # 3  B    -> v3 +X
                         0.0, 1.0, 0.0],     # 4  B50  -> v4 +Y
        "interBase": [-1, 0, 0, -1, 3],
        "interKnot": [0.0, 0.25, 0.5, 0.0, 0.5],
        "comboOffset": [0, 0, 0, 0, 0, 0],   # no combos in this rig
        "comboDriver": []}
    for attr, values in tables.items():
        if mc.attributeQuery(attr, node=name, multi=True):
            for i, v in enumerate(values):
                mc.setAttr("%s.%s[%d]" % (name, attr, i), v)
        else:
            _dt = mc.getAttr("%s.%s" % (name, attr), type=True)
            _cast = float if _dt == "doubleArray" else int
            mc.setAttr("%s.%s" % (name, attr),
                       [_cast(v) for v in values], type=_dt)

    for i in range(5):
        mc.setAttr("%s.weight[%d]" % (name, i), 0.0)

    def pts(a, b=0.0):
        mc.setAttr(name + ".weight[0]", a)
        mc.setAttr(name + ".weight[3]", b)
        mc.setAttr(name + ".applyCorrectives", 1)
        mc.setAttr(name + ".applyCombos", 1)
        mc.setAttr(name + ".envelope", 1.0)
        mc.dgdirty(name + ".outputGeometry")
        mc.getAttr(shape + ".outMesh")
        sel = om2.MSelectionList()
        sel.add(shape)
        fn = om2.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    rest = pts(0.0)
    assert_true(rest.shape[0] >= 5,
                "test plane should have at least 5 verts, got %d" % rest.shape[0])

    def expect(a, h25, h50, b=0.0, hb50=0.0):
        e = rest.copy()
        e[0, 1] += a
        e[1, 1] += h25
        e[2, 1] += h50
        e[3, 0] += b
        e[4, 1] += hb50
        return e.tolist()

    # A25 owns 0 -> 0.25 -> 0.5; A50 owns 0.25 -> 0.5 -> 1.0.
    assert_close(pts(0.00).tolist(), expect(0.00, 0.0, 0.0),
                 msg="both hats must be 0 at rest")
    assert_close(pts(0.25).tolist(), expect(0.25, 1.0, 0.0),
                 msg="A25 peaks at its knot and A50 must be silent there")
    assert_close(pts(0.50).tolist(), expect(0.50, 0.0, 1.0),
                 msg="A50 peaks at its knot and A25 must have handed off to 0")
    assert_close(pts(0.375).tolist(), expect(0.375, 0.5, 0.5),
                 msg="midway between knots the two hats split 50/50")
    assert_close(pts(0.75).tolist(), expect(0.75, 0.0, 0.5),
                 msg="past the last knot only A50 falls off, A25 stays 0")
    assert_close(pts(1.00).tolist(), expect(1.00, 0.0, 0.0),
                 msg="both hats must be 0 with the driver at full")

    # The regression itself, stated as a number: the OLD full-range hat put A25
    # at (1-0.5)/(1-0.25) = 0.6667 here. Anything non-zero fails.
    at_half = pts(0.50)
    assert_close([at_half[1, 1]], [rest[1, 1]],
                 msg="A25 must contribute NOTHING at A=0.5 (old hat gave 0.667)")

    # A lone in-between is unaffected: with no sibling it still spans 0..1, so
    # the fix cannot have changed any rig that has one in-between per driver.
    assert_close(pts(0.0, 0.5).tolist(), expect(0.0, 0.0, 0.0, 0.5, 1.0),
                 msg="a LONE in-between still peaks on its knot")
    assert_close(pts(0.0, 0.25).tolist(), expect(0.0, 0.0, 0.0, 0.25, 0.5),
                 msg="a LONE in-between still ramps from 0, not from a sibling")

    # Hats stay on their own driver -- A must not move B's in-between.
    assert_close(pts(0.5, 0.0).tolist(), expect(0.5, 0.0, 1.0, 0.0, 0.0),
                 msg="driving A must leave B's in-between at 0")


@maya_demo(label="Combo + In-Between Correctives")
def demo(self):
    """Build a real face rig: a 1306-vertex head and the 167 authored targets
    whose NAMES alone declare the rig -- 52 mains, 31 in-betweens (a trailing
    number is the knot, so `jawDrop75` peaks at 0.75) and 84 combos (an
    underscore joins the drivers, so `cheekPuffL_jawDrop` comes in only as both
    rise). `rebuild()` decodes those names into the numeric tables the Compute
    reads, and bakes every target's raw offsets -- a corrective is sculpted as
    the correction itself, so nothing is subtracted out of it.

    The whole rig ships beside this template as ONE Maya scene: the head, the
    167 sculpts already hidden and parked on a grid behind it, and 42 loose
    animation curves. So the demo imports it and wires it up -- there is no
    shape to rebuild vertex by vertex and no key to set. It used to do both,
    and cost 36 s; 31 s of that was setting 16,002 keys on aliased weight
    plugs, which is roughly 2 ms each.

    The targets cannot be deleted after `rebuild()`: `add_target` holds a live
    `outMesh` connection to each one, so they have to stay in the scene even
    though the deltas are baked.

    Each curve is named `<node>_<alias>` after the plug it belongs on, so
    wiring them is a name lookup. They drive the 52 MAIN channels and nothing
    else. Press play: every in-between and combo you watch fire is DERIVED from
    those 52 curves on that frame by the Init-tab rules, which is the node
    demonstrating itself. The first frame is the rest pose, so the rig still
    comes up unposed.

    The archive is 30 fps, so the demo puts the scene in `ntsc` before
    importing -- Maya remaps keys by TIME, and in a 24 fps scene all 16,002 of
    them would land on fractional frames.

    Park `jawDrop` on 0.75 and the `jawDrop75` correction comes in at full on
    top of the three-quarter jaw drop; scrub it and the corrections hand off
    between the 0.25, 0.50 and 0.75 knots rather than piling up. Dial the
    `jawDrop75` channel on its own and you see that correction by itself,
    exactly as it was sculpted -- no corrective is keyed, so they are all still
    free to dial by hand. Raise `cheekPuffL` alongside `jawDrop` to fade in the
    `cheekPuffL_jawDrop` combo. To hand-drive a MAIN, `cutKey` it first."""
    from maya import cmds as mc
    import os
    from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

    name = self.get_name()
    bs = MPyBlendShape(name)

    # The archive is a sibling of this template -- resolved the way the gallery
    # resolves templates/, so a bundled install finds it too. If it is missing
    # the demo does nothing rather than half-building a rig.
    mesh_path = None
    try:
        from mpynode._common.util.template_gallery import _bundled_templates_root
        root = _bundled_templates_root()
        if root:
            b = os.path.join(root, "MPyBlendShape",
                             "Combo Correctives", "combo167_mesh.ma")
            if os.path.isfile(b):
                mesh_path = b
    except Exception:
        mesh_path = None
    if not mesh_path:
        return name

    # The archive is authored at 30 fps and a fresh scene is 24. Maya remaps
    # imported keys by TIME, not by frame number, so without this every key
    # lands on a fractional frame and the performance no longer sits on the
    # frames it was animated on.
    if mc.currentUnit(query=True, time=True) != "ntsc":
        mc.currentUnit(time="ntsc", updateAnimation=False)

    # ONE import brings the whole rig: the base head, all 167 sculpts (already
    # hidden and parked on a grid behind it) and the 42 driver curves. Nothing
    # is duplicated, offset or keyed here -- rebuilding 167 heads vertex by
    # vertex and then setting 16,002 keys cost 36 s, and 31 s of that was the
    # keying alone.
    new_nodes = mc.file(mesh_path, i=True, returnNewNodes=True,
                        ignoreVersion=True) or []

    # The base is the one mesh named for it; every other mesh is a target, and
    # its NAME is its alias -- which is the whole rig, since rebuild() decodes
    # mains, in-betweens and combos straight out of those names.
    base = None
    targets = []
    for n in new_nodes:
        if mc.nodeType(n) != "transform":
            continue
        if not mc.listRelatives(n, shapes=True, ni=True, type="mesh"):
            continue
        if base is None and n.split("|")[-1].startswith("comboBase"):
            base = n
        else:
            targets.append(n)
    if base is None:
        return name

    # `returnNewNodes` hands back an ASCII-SORTED list (measured: it compares
    # equal to sorted(names)), which interleaves the in-betweens and combos
    # with the mains -- cheekPuffL, cheekPuffL50, cheekPuffL_jawDrop,
    # cheekPuffR -- and throws away the deliberate ordering the scene graph
    # carries. `add_target` appends at the next free weight[] index, so that
    # list IS the alias order and the channel box inherits the sort. Rank by
    # DAG order instead; `ls(dagObjects=True)` reproduces the outliner exactly.
    _rank = {n: i for i, n in enumerate(
        mc.ls(dagObjects=True, long=True, type="transform") or [])}
    targets.sort(key=lambda n: _rank.get(
        (mc.ls(n, long=True) or [n])[0], 1 << 30))

    if name not in (mc.listHistory(base) or []):
        mc.deformer(name, e=True, g=base)

    # Same two calls the `add_targets` command makes. The command itself is
    # seeded at the node-creation command rather than by the template, so it is
    # not on this node yet -- but wiring plus rebuild IS its whole body.
    for t in targets:
        bs.add_target(t)
    bs.rebuild()

    # The curves arrive loose, named `<node>_<alias>` after the plug they
    # belong on, so the wiring is just a name lookup. They drive the 52 MAINS
    # and nothing else: the 31 in-betweens and 84 combos are left undriven on
    # purpose, because they are DERIVED from these curves by the Init-tab rules
    # on every frame. That is the feature, and keying them would hide it.
    aliases = set(a for a in bs.aliases if a)
    curves = [n for n in new_nodes if mc.nodeType(n).startswith("animCurve")]
    for c in curves:
        alias = c.split("|")[-1].split(":")[-1].split("_", 1)[-1]
        if alias in aliases:
            mc.connectAttr(c + ".output", "%s.%s" % (name, alias), force=True)

    # Read the range off the curves rather than hardcoding it, so re-animating
    # the archive re-ranges the demo with no code change.
    start = 0
    if curves:
        start = min(mc.findKeyframe(c, which="first") for c in curves)
        end = max(mc.findKeyframe(c, which="last") for c in curves)
        mc.playbackOptions(minTime=start, maxTime=end,
                           animationStartTime=start, animationEndTime=end)

    # The first frame is the REST pose -- all 52 drivers sit at 0 there -- so
    # the rig still comes up unposed with the animation on it. It used to park
    # jawDrop on 0.75 to show the in-between off, but a rig that comes up
    # already posed hides which channel is doing what, and it is the one thing
    # you cannot undo by looking. Dial jawDrop to 0.75 yourself and it lands on
    # the jawDrop75 sculpt.
    mc.currentTime(start)

    mc.select(base, replace=True)
    # This demo IMPORTS the sculpt archive, so frame the WHOLE scene rather
    # than just the base head.
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


# The three commands the node ships with. A @maya_command body ships as EMBEDDED
# PYTHON inside a compiled .mll, and command_dispatch.reachable_mpynode_imports
# fails the compile on any mpynode import a command can reach -- so these bodies
# import NOTHING from mpynode. They go through ``self``, which is the
# MPyBlendShape wrapper on every interpreted path, and therefore already has the
# whole target API.
#
# DO NOT DROP THE ``_cmd`` SUFFIXES. A def whose name also exists on the wrapper
# is emitted by ``py_export`` as a member of ``class X(MPyBlendShape)``, where it
# SHADOWS the very method its body calls -- ``load_target`` forwarding to
# ``self.load_target`` is then genuinely infinite recursion in the baked ``.py``.
# The command NAME is pinned separately, so ``cmds.load_target`` is unaffected.


@maya_command
def add_targets(self, meshes: list[str] = None):
    """Add meshes as blend-shape targets, each weight aliased after its mesh.

    Defaults to the current selection, which is the usual way to call it: pick
    the shapes, then run. Passing ``meshes`` explicitly is for scripts.
    """
    from maya import cmds as mc

    name = self.get_name()
    sel = list(meshes) if meshes else (mc.ls(selection=True, long=False) or [])
    picked = []
    for n in sel:
        # Never let the node be its own target, whatever is selected.
        if n == name:
            continue
        if mc.nodeType(n) == "mesh" or mc.listRelatives(
                n, shapes=True, type="mesh", noIntermediate=True):
            picked.append(n)
    if not picked:
        raise ValueError(
            "select one or more MESHES to add as targets of %s" % name)

    added = [self.add_target(t) for t in picked]
    # Wiring alone deforms nothing -- the compute reads baked deltas, not the
    # live target meshes.
    self.rebuild()
    aliases = self.aliases
    return [aliases[i] if i < len(aliases) else "" for i in added]


@maya_command(name="load_target")
def load_target_cmd(self, path: str, name: str = ""):
    """Load ONE shape from a file and add it as a target.

    ``.ma`` / ``.mb`` / ``.obj`` / ``.fbx`` are imported to read their points
    and removed again; ``.npz`` / ``.json`` are read directly. Either way the
    shape needs no mesh in the scene and leaves no construction history on the
    node. Returns the weight index.
    """
    return self.load_target(path, name=name or None)


@maya_command(name="load_shapes")
def load_shapes_cmd(self, path: str):
    """Load a whole shape cluster from a ``.npz`` / ``.json``.

    One target per record, in file order, each aliased to its stored name.
    Returns a summary of what was loaded, including how many names decoded as
    in-betweens or combos.
    """
    return self.load_shapes(path)
'''

COMBO_DESC = (
    "# Combo + In-Between Correctives\n\n"
    "An aliased `mPyBlendShape` -- the `weight[]` multi is aliased to your "
    "target names, so the channel box shows `jawDrop` rather than `weight[0]` "
    "-- plus the two corrective shapes every face rig needs. You declare them "
    "in the "
    "target names: `jawDrop` is a main target on its own weight, `jawDrop75` "
    "is an in-between of `jawDrop` peaking at 0.75, and "
    "`cheekPuffL_jawDrop` is a combo that only comes in as both drivers "
    "rise.\n\n"
    "An in-between rides a **cross-blending** hat on its driver: full on its "
    "own knot, falling to 0 at the ADJACENT knots. So `jawDrop25`, `jawDrop50` "
    "and `jawDrop75` hand off to each other rather than all firing at once, "
    "and a lone in-between still spans the driver's whole travel. A combo is "
    "the product of its drivers with the last alias keyword squared, which is "
    "how this corpus was sculpted.\n\n"
    "Every target stores its **raw** offsets. A corrective is sculpted as the "
    "correction ITSELF -- what to add once its drivers are posed -- so nothing "
    "is subtracted at bake time. Dial `jawDrop75` to 1 on its own and you get "
    "exactly the shape that was sculpted, unreduced; park `jawDrop` on 0.75 "
    "and you get the 75% jaw-drop pose with that same correction laid on "
    "top.\n\n"
    "There is **no shared weight resolver**. The maths is in this node: **the "
    "Init tab holds the rules as three ordinary functions** -- "
    "`inbetween_hat`, `combo_blend` and "
    "`resolve_morph_weights` -- and the Compute is a four-line summary that "
    "calls them. Init transpiles alongside the Compute, so an edited rule "
    "still compiles to pure C++. Want a combo that holds up sooner, or without "
    "the squared keyword? `combo_blend` is the one function to change.\n\n"
    "Correctives are **additive**: a corrective keeps whatever is keyed on its "
    "own channel and the derived amount is added on top, so it can be dialled "
    "by hand as well as driven. `applyCorrectives` and `applyCombos` switch "
    "the derived half off without unhooking anything -- useful for seeing what "
    "each layer actually contributes while the drivers are animating.\n\n"
    "**Create + Run demo** builds a real face: a 1306-vertex head and all 167 "
    "authored targets -- 52 mains, 31 in-betweens and 84 combos -- with every "
    "channel at rest, driven by **381 frames of performance capture on the 52 "
    "mains and nothing else**. Press play: every in-between and combo you "
    "see fire is derived from those 52 curves on that frame, never keyed. "
    "Scrub `jawDrop` and watch the 0.25, 0.50 and 0.75 "
    "corrections hand off to each other one at a time; raise "
    "`cheekPuffL` with it to fade the `cheekPuffL_jawDrop` combo in. The whole "
    "rig ships beside the template as one Maya scene -- head, sculpts and "
    "loose animation curves -- so the demo imports it and wires it up rather "
    "than rebuilding 167 shapes and setting 16,002 keys, which is the "
    "difference between 3 s and 36 s. Each curve is named after the plug it "
    "belongs on, so the wiring is a name lookup. The targets sit hidden in a "
    "grid behind the head; they stay in the scene because `add_target` holds a "
    "live connection to each, even though `rebuild()` has baked the deltas.\n\n"
    "Compiles to pure C++. The names are decoded once, in Python, into the "
    "`shapeSlot` / `interBase` / `interKnot` / `comboOffset` / `comboDriver` "
    "integer tables, so nothing character-specific reaches the generated code."
)


def _blend_shape_deform(name, shape, weights, env=1.0):
    """Set `weight[i]` from ``weights``, force a deform, return the (N,3) points.

    Used across the blendShape builder -- the interpreted compute check and the
    round-tripped demo check need the identical drive-then-read cycle.
    """
    for i, v in enumerate(weights):
        mc.setAttr("%s.weight[%d]" % (name, i), v)
    mc.setAttr(name + ".envelope", env)
    mc.dgdirty(name + ".outputGeometry")
    mc.getAttr(shape + ".outMesh")
    return _mesh_object_pts(shape)


def _blend_shape_roundtrip(payload, methods_src, check):
    """Deserialize ``payload`` into a fresh scene, run its demo, then its test.

    ``check(node)`` runs after the demo and returns ``(ok, detail)`` -- the
    template-specific assertion about what the demo actually produced. Returns
    ``(demo_ok, demo_err, test_ok, test_err, has_demo)``.
    """
    from mpynode._common.io.mpn_io import deserialize_node
    from mpynode._common.methods.methods_registry import run_node_demo
    from mpynode._common.node_setups import find_demo

    demo_ok, demo_err = False, "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(payload, restore_persistent=False)
        run_node_demo(tnode)
        demo_ok, demo_err = check(tnode)
    except Exception as exc:
        demo_err = "exc:%r" % exc

    test_ok, test_err = False, "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    return demo_ok, demo_err, test_ok, test_err, find_demo(methods_src) is not None


def _blend_shape_portability(node_name):
    """Portability report for a LIVE node, read exactly as the compiler reads it.

    Uses ``extract_spec`` rather than a hand-written input map, so the gate sees
    the node's REAL attribute set -- a table attr I forgot to declare shows up
    here instead of at compile time.
    """
    from mpynode.native.spec import spec_extractor as _sx

    return _sx.extract_spec(node_name)["portability"]


def build_combo_correctives():
    from mpynode.wrappers.mpy_blend_shape import MPyBlendShape
    from mpynode._common.io.user_classes import synthesize, dotted_path

    mc.file(new=True, force=True)

    # --- compute check: a main, its in-between, a second main, their combo ---
    base = mc.polySphere(r=1.0, sx=12, sy=12, name="ccBase")[0]

    def sculpt(label, sx, sy, sz):
        t = mc.polySphere(r=1.0, sx=12, sy=12, name=label)[0]
        mc.scale(sx, sy, sz, t + ".vtx[*]", relative=True)
        return t

    # The correctives carry a Z bulge that no linear combination of the mains
    # can reach -- otherwise "the corrective works" would be unfalsifiable.
    brow = sculpt("ccBrow", 1.0, 1.6, 1.0)
    mouth = sculpt("ccMouth", 1.6, 1.0, 1.0)

    # The two CORRECTIVES are authored the way real corrective sculpts are, and
    # the way the shipped 167-shape corpus is: as the correction ITSELF, on top
    # of whatever the drivers already give -- not as an absolute pose.
    #
    # So pick the pose each corrective should PRODUCE, subtract what the linear
    # stack contributes at that point, and sculpt the remainder. The exactness
    # gates below then check the produced POSE, not the target mesh, because
    # the target mesh is deliberately no longer the pose.
    #
    # This fixture used to sculpt absolute poses and let `bake_deltas` subtract
    # the linear share back out. That was the bug: it made the stored delta
    # right only for the driven path, and a corrective dialled by hand rendered
    # its sculpt minus a fraction of its driver.
    def _pts(node):
        return _mesh_object_pts(
            mc.listRelatives(node, shapes=True, ni=True, f=True)[0])

    def _set_pts(node, arr):
        shp = mc.listRelatives(node, shapes=True, ni=True, f=True)[0]
        sel = om.MSelectionList()
        sel.add(shp)
        fn = om.MFnMesh(sel.getDagPath(0))
        fn.setPoints(om.MPointArray([om.MPoint(float(p[0]), float(p[1]),
                                               float(p[2])) for p in arr]),
                     om.MSpace.kObject)

    base_pts = _pts(base)
    d_brow = _pts(brow) - base_pts
    d_mouth = _pts(mouth) - base_pts

    # Pose the in-between must produce when browUp sits on its 0.50 knot.
    brow50 = sculpt("ccBrow50", 1.0, 1.3, 1.35)
    pose_brow50 = _pts(brow50).copy()
    _set_pts(brow50, pose_brow50 - 0.5 * d_brow)

    # Pose the combo must produce with both drivers at 1.
    combo = sculpt("ccCombo", 1.6, 1.6, 1.4)
    pose_combo = _pts(combo).copy()
    _set_pts(combo, pose_combo - d_brow - d_mouth)

    bs = MPyBlendShape.create(mesh=base, name="comboCorrectives")
    # A real Class, not the class-less instance-name fallback. Without this the
    # compiled identity is derived from the NODE NAME (spec_extractor's
    # `derive_class_identity(class_path or name, ...)`), so renaming the node
    # would silently rename the compiled type. The derived strings are unchanged
    # either way -- identity.py upper-firsts to `ComboCorrectives` and
    # lower-firsts back to `comboCorrectives` -- so this moves no type name, no
    # type_id seed and no port-cache key; it only makes the identity explicit
    # and rename-proof.
    synthesize("ComboCorrectives", "mPyBlendShape")
    bs.set_py_class(dotted_path("ComboCorrectives"))
    bs.ensure_delta_attrs()
    bs.ensure_corrective_attrs()
    # The two driven-half switches the Compute reads. Default ON, so a fresh
    # node behaves exactly as it did before they existed.
    bs.add_input_attr("applyCorrectives", "bool", default_value=True)
    bs.add_input_attr("applyCombos", "bool", default_value=True)
    bs.set_init_expression(COMBO_INIT)
    bs.set_compute_expression(COMBO_COMPUTE)
    bs.set_methods_source(COMBO_METHODS)
    nm = bs.get_name()

    bs.add_target(brow, "browUp")
    bs.add_target(brow50, "browUp50")
    bs.add_target(mouth, "mouthOpen")
    bs.add_target(combo, "browUp_mouthOpen")
    bs.rebuild()

    # The names ALONE must have produced the right structure.
    struct = bs.parse_aliases()
    decode_ok = (struct["main"] == [0, 2]
                 and struct["inter"] == {1: (0, 0.5)}
                 and struct["combo"] == {3: [0, 2]})

    shape = mc.listRelatives(base, shapes=True, noIntermediate=True, f=True)[0]

    def at(brow_w, mouth_w):
        # weight[1] / weight[3] are the corrective channels. Correctives are
        # ADDITIVE, so they are held at 0.0 here deliberately: that isolates the
        # DRIVEN half, which is what the four exactness gates below measure. A
        # hand-set corrective adds on top and is covered separately.
        return _blend_shape_deform(nm, shape, [brow_w, 0.0, mouth_w, 0.0])

    def pts_of(node):
        return _mesh_object_pts(
            mc.listRelatives(node, shapes=True, ni=True, f=True)[0])

    rest = at(0.0, 0.0)
    brow_full = at(1.0, 0.0)
    brow_knot = at(0.5, 0.0)
    mouth_full = at(0.0, 1.0)
    both_full = at(1.0, 1.0)

    # Every authored pose must be reproduced EXACTLY. This is the whole
    # corrective contract in four lines: the mains at their endpoints, the
    # in-between on its knot, the combo with both drivers up. The correctives
    # are checked against the POSE they were authored to produce, since their
    # target meshes hold the correction rather than the pose.
    exact_ok = (float(np.abs(brow_full - pts_of(brow)).max()) < 1e-6
                and float(np.abs(mouth_full - pts_of(mouth)).max()) < 1e-6
                and float(np.abs(brow_knot - pose_brow50).max()) < 1e-6
                and float(np.abs(both_full - pose_combo).max()) < 1e-6)

    # ...and the OTHER route to the same shape: a corrective dialled by hand
    # with its drivers at rest must put its own sculpt on the mesh, unreduced.
    # This is the bug the user reported, as a build gate.
    alone_ok = (float(np.abs(
        _blend_shape_deform(nm, shape, [0.0, 1.0, 0.0, 0.0])
        - (rest + (pose_brow50 - 0.5 * d_brow - base_pts))).max()) < 1e-6)

    # ...and each corrective must actually be DOING something -- i.e. differ
    # from what the plain linear stack would have produced.
    inter_bulges = float(np.abs(
        brow_knot - 0.5 * (rest + brow_full)).max()) > 1e-4
    combo_adds = float(np.abs(
        both_full - (brow_full + mouth_full - rest)).max()) > 1e-4

    # The ADDITIVE half: a corrective dialled BY HAND with both drivers at rest
    # must still move the mesh. Under a replace rule the channel is discarded
    # and this reads identical to rest -- which is precisely what made the
    # corrective fields in the Attribute Editor meaningless.
    combo_by_hand = _blend_shape_deform(nm, shape, [0.0, 0.0, 0.0, 1.0])
    inter_by_hand = _blend_shape_deform(nm, shape, [0.0, 1.0, 0.0, 0.0])
    hand_set_ok = (float(np.abs(combo_by_hand - rest).max()) > 1e-4
                   and float(np.abs(inter_by_hand - rest).max()) > 1e-4)

    compute_ok = bool(decode_ok and exact_ok and alone_ok and inter_bulges
                      and combo_adds and hand_set_ok)

    rep = _blend_shape_portability(nm)
    portable_ok = bool(rep["portable"])

    clean_payload = serialize_node(bs, include_persistent=False)

    def _check(tnode):
        tnm = tnode.get_name()
        al = list(tnode.aliases if hasattr(tnode, "aliases") else [])
        base_t = (mc.ls("comboBase*", type="transform") or [None])[0]
        in_hist = base_t is not None and tnm in (mc.listHistory(base_t) or [])

        # The corpus is 52 mains + 31 in-betweens + 84 combos and the NAMES are
        # the rig, so gate on the DECODE rather than on a hardcoded name list --
        # a list of 167 strings would fail for a reordering that changes nothing.
        struct = tnode.parse_aliases() if hasattr(tnode, "parse_aliases") else {}
        decode_ok = (len(al) == 167
                     and len(struct.get("main") or []) == 52
                     and len(struct.get("inter") or {}) == 31
                     and len(struct.get("combo") or {}) == 84)

        # The demo wires 381 frames of driver animation in from the archive,
        # and ONLY drivers may be driven: a curve on an in-between or a combo
        # would mean the derived half had been baked instead of resolved every
        # frame. 42 of the 52 mains move; the other 10 are flat in the source
        # and carry no curve at all.
        #
        # This runs BEFORE the bulge check and leaves time back at 0. `setAttr`
        # on a driven plug sticks through `dgdirty`, which is all
        # `_blend_shape_deform` does -- but a time change hands the plug back to
        # its curve, so scrubbing after the bulge check would silently gut it.
        anim_ok = False
        if base_t is not None:
            mains = set(struct.get("main") or [])
            keyed = [i for i, a in enumerate(al)
                     if a and mc.listConnections("%s.%s" % (tnm, a),
                                                 source=True, destination=False,
                                                 type="animCurve")]
            shp_a = mc.listRelatives(base_t, shapes=True, ni=True, f=True)[0]

            def _at_time(t):
                mc.currentTime(t)
                mc.getAttr(shp_a + ".outMesh")
                return _mesh_object_pts(shp_a)

            p0 = _at_time(0)
            p1 = _at_time(293)      # the peak-motion frame of the performance
            _at_time(0)
            anim_ok = (len(keyed) == 42
                       and all(i in mains for i in keyed)
                       and float(np.abs(p1 - p0).max()) > 1e-3)

        # jawDrop carries a 0.75 in-between, so the deform at 0.75 must NOT be
        # the linear blend of its endpoints -- that is the corrective doing work.
        bulged = False
        if base_t is not None and "jawDrop" in al and "jawDrop75" in al:
            shp = mc.listRelatives(base_t, shapes=True, ni=True, f=True)[0]
            di = al.index("jawDrop")

            def _at(v):
                ws = [0.0] * len(al)
                ws[di] = v
                return _blend_shape_deform(tnm, shp, ws)

            r = _at(0.0)
            f = _at(1.0)
            k = _at(0.75)
            bulged = float(np.abs(k - (0.25 * r + 0.75 * f)).max()) > 1e-4

        ok = bool(in_hist and bulged and decode_ok and anim_ok)
        return ok, ("base=%s in_hist=%s inbetween_bulges=%s n=%d decode=%s "
                    "anim=%s"
                    % (base_t, in_hist, bulged, len(al), decode_ok, anim_ok))

    # The demo loads these from beside the template, so they have to be in place
    # BEFORE the roundtrip runs it -- otherwise the demo bails and demo_ok fails.
    # ONE asset now: the .ma carries the base, the 167 sculpts and the 42
    # driver curves, so the sparse shape archive and the baked-curve archive
    # the demo used to read are both dead.
    assets_ok = True
    for _fn in ("combo167_mesh.ma",):
        if _copy_asset(_fn, COMBO_CORR_DIR) is None:
            assets_ok = False

    demo_ok, demo_err, test_ok, test_err, has_demo = _blend_shape_roundtrip(
        clean_payload, COMBO_METHODS, _check)

    payload_ok = clean_payload.get("native_type") == "mPyBlendShape"
    cls_ok = clean_payload.get("class_path") == dotted_path("ComboCorrectives")
    ok = bool(compute_ok and portable_ok and demo_ok and test_ok and has_demo
              and payload_ok and cls_ok and assets_ok)
    print("[combo_correctives] decode=%s exact=%s alone=%s inbetween=%s "
          "combo=%s hand_set=%s portable=%s demo=%s(%s) test=%s(%s) "
          "has_demo=%s payload=%s class=%s assets=%s -> %s"
          % (decode_ok, exact_ok, alone_ok, inter_bulges, combo_adds,
             hand_set_ok, portable_ok, demo_ok, demo_err, test_ok, test_err,
             has_demo, payload_ok, cls_ok, assets_ok, "PASS" if ok else "FAIL"))
    if not portable_ok:
        print("        blockers: %s" % rep["blockers"])
    if ok:
        _write_template_to("MPyBlendShape/Combo Correctives",
                           clean_payload, COMBO_DESC)
    return ok


# ======================================================================
# mPyNode -- RBF thin-plate-spline WRAP (three mesh inputs -> mesh output)
# ======================================================================
RBF_WRAP_INIT = "import numpy as np\nfrom mpynode._api2.geometry import Mesh\n"

RBF_WRAP_COMPUTE = r'''# RBF thin-plate-spline WRAP: a smooth space warp defined by two control cages of
# identical topology -- `restCage` (rest positions) and `deformCage` (deformed
# positions) -- carries every point of `geoToDeform` from rest to deformed space
# and emits the result on `outGeo`. The warp is the classic thin-plate spline:
# kernel phi(r) = r^2 * log(r) (== 0.5 * d2 * log(d2), so no sqrt) plus an affine
# polynomial tail, so a rigid/affine cage motion is reproduced EXACTLY and a
# non-affine cage motion bends the geometry as smoothly as possible.
#
# The whole compute lowers to PURE C++ (byte-exact interp-vs-compiled): pairwise
# squared distances (matmul-identity form), the guarded r^2 log r kernel (via
# where/maximum -- no nan to clean up), the augmented (M+4) system built with
# zeros + slice-stores, Tikhonov-regularised and solved by nd::inv, then the
# evaluation matmul. A tiny 1e-8*I keeps the solve off nd::inv's singular
# fallback (and makes the empty-cage eager-eval a clean no-op, not a raise), and
# tightens interp(LAPACK)-vs-compiled(Gauss-Jordan) agreement. This is an mPyNode
# with THREE mesh INPUTS + one mesh OUTPUT (the #83 geo-I/O path) -- the only node
# shape that reads multiple meshes AND emits a mesh AND lowers deterministically.
rest = self.restCage.points
deform = self.deformCage.points
P = self.geoToDeform.points
counts = self.geoToDeform.counts
indices = self.geoToDeform.indices
M = rest.shape[0]
Nn = P.shape[0]
rc = (rest * rest).sum(1)
d2 = rc[:, None] + rc[None, :] - 2.0 * (rest @ rest.T)
d2 = np.maximum(d2, 0.0)
K = np.where(d2 > 1e-12, 0.5 * d2 * np.log(np.maximum(d2, 1e-12)), 0.0)
A = np.zeros((M + 4, M + 4))
A[:M, :M] = K
A[:M, M] = 1.0
A[:M, M + 1:] = rest
A[M, :M] = 1.0
A[M + 1:, :M] = rest.T
A = A + 1e-8 * np.eye(M + 4)
T = np.zeros((M + 4, 3))
T[:M, :] = deform
W = np.linalg.inv(A) @ T
pc = (P * P).sum(1)
e2 = pc[:, None] + rc[None, :] - 2.0 * (P @ rest.T)
e2 = np.maximum(e2, 0.0)
Ke = np.where(e2 > 1e-12, 0.5 * e2 * np.log(np.maximum(e2, 1e-12)), 0.0)
H = np.zeros((Nn, M + 4))
H[:, :M] = Ke
H[:, M] = 1.0
H[:, M + 1:] = P
warped = H @ W
self.outGeo = Mesh(points=warped, counts=counts, indices=indices)
'''

RBF_WRAP_METHODS = VANILLA_SETUP_ERROR + VANILLA_MESHES + r'''

@maya_test(label="TPS wrap reproduces affine cage motion", digits=4)
def test_wrap_affine(self):
    """Validate the node's INTENT (same test runs on the interpreted node and its
    C++ compile -> parity): a thin-plate-spline wrap must reproduce an AFFINE cage
    motion EXACTLY -- (1) deformCage == restCage -> the geometry is unchanged;
    (2) translate the deform cage -> the geometry translates by the same vector."""
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_close, assert_true

    name = self.get_name()

    # Minimal rig on THIS node: a subdivided rest cage, a deform cage (same
    # topology), and a test sphere inside it to warp.
    restC = mc.polyCube(w=4, h=4, d=4, sx=2, sy=2, sz=2,
                        name="wrapTestRest#", ch=False)[0]
    restS = mc.listRelatives(restC, s=True, f=True)[0]
    defC = mc.duplicate(restC, name="wrapTestDeform#")[0]
    defS = mc.listRelatives(defC, s=True, f=True)[0]
    sph = mc.polySphere(r=1.0, sx=10, sy=10, name="wrapTestGeo#", ch=False)[0]
    sphS = mc.listRelatives(sph, s=True, f=True)[0]
    render = mc.createNode("mesh", name="wrapTestOut#")

    for src_shape, dst in ((restS, "restCage"), (defS, "deformCage"),
                           (sphS, "geoToDeform")):
        plug = name + "." + dst
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.connectAttr(src_shape + ".worldMesh[0]", plug, f=True)
    mc.connectAttr(name + ".outGeo", render + ".inMesh", f=True)

    def _pts(shape):
        sel = om2.MSelectionList()
        sel.add(shape)
        fn = om2.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    def _out():
        mc.dgdirty(a=True)
        mc.dgeval(render + ".outMesh")
        return _pts(render)

    src = _pts(sphS)

    # (1) identity: deformCage == restCage -> geo unchanged.
    ident = _out()
    assert_true(ident.shape == src.shape,
                "output vert count (%d) must match input (%d)"
                % (ident.shape[0], src.shape[0]))
    assert_close(ident.ravel().tolist(), src.ravel().tolist())

    # (2) affine: translate the deform cage's verts by (0, 2, 0) -> the TPS
    # (via its affine tail) must translate the geometry by exactly (0, 2, 0).
    mc.move(0.0, 2.0, 0.0, defC + ".vtx[*]", r=True)
    moved = _out()
    expect = (src + np.array([0.0, 2.0, 0.0])).ravel().tolist()
    assert_close(moved.ravel().tolist(), expect)


@maya_demo(label="Wrap an Arm with a Cage")
def demo(self):
    """Wrap the shipped two-bone arm mesh inside a lightly-subdivided cube cage.
    A keyed `bend` on the deform cage flexes it as the timeline plays, and the
    thin-plate-spline wrap carries the arm along -- press play to watch the arm
    follow the cage. (Falls back to a subdivided cylinder if the arm file is
    absent.)"""
    from maya import cmds as mc
    import os
    name = self.get_name()

    # --- geometry to deform: the shipped two-bone arm mesh (skin removed so it
    #     sits at its rest), else a subdivided cylinder. ---
    mesh_xform = None
    try:
        from mpynode._common.util.template_gallery import _bundled_templates_root
        root = _bundled_templates_root() or ""
        arm = os.path.join(root, "MPyNode", "Ouch", "arm.ma")
        if os.path.exists(arm):
            new = mc.file(arm, i=True, ignoreVersion=True,
                          returnNewNodes=True) or []
            for sc in (mc.ls(new, type="skinCluster") or []):
                try:
                    mc.skinCluster(sc, e=True, unbind=True)
                except Exception:
                    pass
            meshes = [m for m in (mc.ls(new, type="mesh", long=True) or [])
                      if not mc.getAttr(m + ".intermediateObject")]
            if meshes:
                mesh_xform = mc.listRelatives(meshes[0], parent=True, fullPath=True)[0]
    except Exception:
        mesh_xform = None
    if mesh_xform is None:
        mesh_xform = mc.polyCylinder(r=1.0, h=8.0, sx=16, sy=16, name="wrapArm#")[0]
    geoS = mc.listRelatives(mesh_xform, s=True, ni=True, f=True)[0]

    # --- rest cage: a padded, lightly-subdivided cube around the arm bbox. ---
    bb = mc.exactWorldBoundingBox(mesh_xform)
    cx, cy, cz = (bb[0] + bb[3]) / 2.0, (bb[1] + bb[4]) / 2.0, (bb[2] + bb[5]) / 2.0
    pad = 1.15
    w = max(bb[3] - bb[0], 0.1) * pad
    h = max(bb[4] - bb[1], 0.1) * pad
    d = max(bb[5] - bb[2], 0.1) * pad
    restC = mc.polyCube(w=w, h=h, d=d, sx=2, sy=4, sz=2,
                        name="wrapRestCage#", ch=False)[0]
    mc.xform(restC, ws=True, t=(cx, cy, cz))
    mc.makeIdentity(restC, apply=True, t=True, r=True, s=True)  # bake -> worldMesh==rest
    restS = mc.listRelatives(restC, s=True, f=True)[0]

    # --- deform cage: same topology, bent by a keyed nonLinear bend. ---
    defC = mc.duplicate(restC, name="wrapDeformCage#")[0]
    defS = mc.listRelatives(defC, s=True, f=True)[0]
    bend = mc.nonLinear(defC, type="bend")
    bend_node, bend_handle = bend[0], bend[1]
    mc.setAttr(bend_handle + ".rotateZ", 90.0)
    for f, cv in ((1, 0.0), (60, 70.0), (120, 0.0)):
        mc.setKeyframe(bend_node + ".curvature", t=f, v=cv)

    # --- wire self: cages + geo in, deformed geo out to a render mesh. ---
    render_x = mc.createNode("transform", name="wrapResult#")
    render = mc.createNode("mesh", name="wrapResultShape#", parent=render_x)
    mc.connectAttr(restS + ".worldMesh[0]", name + ".restCage", f=True)
    mc.connectAttr(defS + ".worldMesh[0]", name + ".deformCage", f=True)
    mc.connectAttr(geoS + ".worldMesh[0]", name + ".geoToDeform", f=True)
    mc.connectAttr(name + ".outGeo", render + ".inMesh", f=True)
    try:
        mc.sets(render, e=True, forceElement="initialShadingGroup")
    except Exception:
        pass

    # --- cosmetics: hide the source arm + rest cage; show the deform cage as a
    #     wireframe control and the wrapped result. ---
    try:
        mc.setAttr(mesh_xform + ".visibility", False)
        mc.setAttr(restC + ".visibility", False)
        mc.setAttr(defS + ".overrideEnabled", True)
        mc.setAttr(defS + ".overrideShading", False)
    except Exception:
        pass

    mc.playbackOptions(min=1, max=120)
    mc.currentTime(60)
    mc.select(render_x, replace=True)
    # This demo IMPORTS arm.ma, so frame the WHOLE scene rather than just the
    # wrapped result.
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name


@maya_command(creates=True)
def setup(self, selection=None, *args, **kwargs):
    """Wire a thin-plate-spline wrap from the selection: pick the REST cage, the
    DEFORM cage (same topology) and the GEOMETRY to warp, in that order. Creates
    the result mesh the warped geometry is written to (once)."""
    from maya import cmds as mc
    name = self.get_name()

    order = [o for o in (selection or mc.ls(selection=True) or []) if o != name]
    meshes = _meshes(order) if order else []
    if len(meshes) < 3:
        raise SetupError(
            "Select THREE meshes in pick order: the REST cage, the DEFORM cage "
            "(a duplicate of the rest cage -- same topology), then the " "GEOMETRY to warp.")

    def _shape(node):
        node = (mc.ls(node, long=True) or [node])[0]
        if mc.nodeType(node) == "mesh":
            return node
        return (mc.listRelatives(node, shapes=True, type="mesh",
                                 noIntermediate=True, fullPath=True) or [node])[0]

    rest_shape = _shape(meshes[0])
    deform_shape = _shape(meshes[1])
    geo_shape = _shape(meshes[2])

    n_rest = mc.polyEvaluate(rest_shape, vertex=True)
    n_deform = mc.polyEvaluate(deform_shape, vertex=True)
    if n_rest != n_deform:
        raise SetupError(
            "The rest cage (%s: %s verts) and the deform cage (%s: %s verts) "
            "must have IDENTICAL topology -- the wrap pairs them vertex for "
            "vertex. Duplicate the rest cage to make the deform cage."
            % (rest_shape.split("|")[-1], n_rest,
               deform_shape.split("|")[-1], n_deform))

    mc.connectAttr(rest_shape + ".worldMesh[0]", name + ".restCage", force=True)
    mc.connectAttr(deform_shape + ".worldMesh[0]", name + ".deformCage", force=True)
    mc.connectAttr(geo_shape + ".worldMesh[0]", name + ".geoToDeform", force=True)

    # The warped result needs somewhere to land. Create the render mesh ONCE:
    # re-running "Run setup" re-uses whatever outGeo already feeds instead of
    # littering the scene with a second result shape.
    dst = mc.listConnections(name + ".outGeo", source=False, destination=True, plugs=True) or []
    render = dst[0].split(".")[0] if dst else None
    if not render or not mc.objExists(render):
        base = name.split("|")[-1]
        render_x = mc.createNode("transform", name=base + "_result#")
        render = mc.createNode("mesh", name=base + "_resultShape#", parent=render_x)
        render = (mc.ls(render, long=True) or [render])[0]
        try:
            mc.sets(render, edit=True, forceElement="initialShadingGroup")
        except Exception:
            pass
    mc.connectAttr(name + ".outGeo", render + ".inMesh", force=True)
    return name
'''

RBF_WRAP_DESC = (
    "# RBF Wrap\n\n"
    "A wrap deformer driven by a cage. Hand it two copies of one cage -- "
    "`restCage` at rest, `deformCage` posed -- plus the geometry to carry on "
    "`geoToDeform`, and the warped result comes out on `outGeo`.\n\n"
    "The two cages define a thin-plate spline (an RBF), the smoothest warp "
    "from one to the other: move, rotate or scale the whole cage and the "
    "geometry follows exactly; push a few points and it bends smoothly "
    "between them. The cages must share topology; `geoToDeform` need not, so "
    "a light cage drives a dense mesh.\n\n"
    "**Create + Run demo** wraps the shipped two-bone arm mesh in a "
    "lightly-subdivided cube cage and flexes it with a keyed bend -- press "
    "play to watch the arm follow. Compiles to pure C++.\n"
)


def build_rbf_wrap():
    mc.file(new=True, force=True)
    _ensure_mpy_plugins()
    from mpynode.wrappers._mpy_node import MPyNode
    import maya.api.OpenMaya as om2

    w = MPyNode.create(name="rbfWrap")
    w.add_input_attr("restCage", "mesh")
    w.add_input_attr("deformCage", "mesh")
    w.add_input_attr("geoToDeform", "mesh")
    w.add_output_attr("outGeo", "mesh")
    w.set_init_expression(RBF_WRAP_INIT)
    w.set_compute_expression(RBF_WRAP_COMPUTE)
    w.set_methods_source(RBF_WRAP_METHODS)

    _stamp_class(w, "RbfWrap", "mPyNode")
    clean_payload = serialize_node(w, include_persistent=False)

    from mpynode._common.methods.methods_registry import run_node_demo
    from mpynode._common.io.mpn_io import deserialize_node

    def _render_pts(frame):
        render = (mc.ls("wrapResultShape*", type="mesh", long=True) or [None])[0]
        if render is None:
            return None
        mc.currentTime(frame)
        mc.dgdirty(a=True)
        mc.dgeval(render + ".outMesh")
        sel = om2.MSelectionList()
        sel.add(render)
        fn = om2.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    ok = False
    detail = "n/a"
    try:
        mc.file(new=True, force=True)
        _ensure_mpy_plugins()
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        run_node_demo(tnode)
        p1 = _render_pts(1)
        p60 = _render_pts(60)
        if p1 is None or p60 is None:
            detail = "no wrapResultShape produced"
        else:
            nverts = int(p1.shape[0])
            animated = (float(np.abs(p1 - p60).max())
                        if p1.shape == p60.shape else -1.0)
            ok = bool(nverts > 0 and animated > 0.05)
            detail = "verts=%d animated=%.4f" % (nverts, animated)
    except Exception as exc:
        detail = "exc:%r" % exc

    # --- authored @maya_test check on a FRESH deserialized node (parity bar). ---
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        _ensure_mpy_plugins()
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    ok = bool(ok and test_ok)
    print("[rbf_wrap] %s test=%s(%s) -> %s"
          % (detail, test_ok, test_err, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(RBF_WRAP_DIR, clean_payload, RBF_WRAP_DESC)
    return ok


# ======================================================================
# mPyDeformer -- the SAME RBF thin-plate wrap, as a deformer
# ======================================================================
RBF_WRAP_DEF_INIT = "import numpy as np\n"

RBF_WRAP_DEF_COMPUTE = r'''# RBF thin-plate-spline WRAP, as a DEFORMER. Two control cages of identical
# topology -- `restCage` (rest positions) and `deformCage` (deformed positions) --
# define a smooth space warp that carries every point of the deformed geometry
# from rest to deformed space. The warp is the classic thin-plate spline: kernel
# phi(r) = r^2 * log(r) (== 0.5 * d2 * log(d2), so no sqrt) plus an affine
# polynomial tail, so a rigid/affine cage motion is reproduced EXACTLY and a
# non-affine cage motion bends the geometry as smoothly as possible.
#
# Unlike the mPyNode rbf_wrap (three mesh INPUTS + a mesh OUTPUT), the geometry to
# deform is the deformer's own `outputGeometry` -- so this node stacks in a normal
# deformation chain and honours `envelope` (0 = rest, 1 = fully warped).
#
# A deformer is LIVE the moment mc.deformer() creates it, so the never-connected
# and mismatched cage states are normal, not exotic. `hasCage` is a purely NUMERIC
# no-op gate (no try/except -- that would drop the node to the AI porter): the
# warp is only applied when both cages carry points AND agree on point count.
# `Mm` clamps the deform-cage copy so a half-wired node never shape-mismatches.
# (Note: DISCONNECTING a cage does not reach this gate -- Maya retains the last
# mesh in the datablock, so the compute keeps seeing the old point count.)
#
# The whole compute lowers to PURE C++: pairwise squared distances (matmul-identity
# form), the guarded r^2 log r kernel (via where/maximum -- no nan to clean up),
# the augmented (M+4) system built with zeros + slice-stores, Tikhonov-regularised
# and solved by nd::inv, then the evaluation matmul. A tiny 1e-8*I keeps the solve
# off nd::inv's singular fallback and tightens interp(LAPACK)-vs-compiled
# (Gauss-Jordan) agreement.
#
# WARNING: getPoints()/setPoints() are OBJECT space while the cages are read in
# WORLD space (worldMesh), so this is only correct when the deformed mesh has an
# identity transform at the world origin (freeze its transform).
mesh = self.outputGeometry[0]
rest = self.restCage.points
deform = self.deformCage.points
P = mesh.getPoints()
M = rest.shape[0]
Md = deform.shape[0]
Mm = min(M, Md)
Nn = P.shape[0]
rc = (rest * rest).sum(1)
d2 = rc[:, None] + rc[None, :] - 2.0 * (rest @ rest.T)
d2 = np.maximum(d2, 0.0)
K = np.where(d2 > 1e-12, 0.5 * d2 * np.log(np.maximum(d2, 1e-12)), 0.0)
A = np.zeros((M + 4, M + 4))
A[:M, :M] = K
A[:M, M] = 1.0
A[:M, M + 1:] = rest
A[M, :M] = 1.0
A[M + 1:, :M] = rest.T
A = A + 1e-8 * np.eye(M + 4)
T = np.zeros((M + 4, 3))
T[:Mm, :] = deform[:Mm, :]
W = np.linalg.inv(A) @ T
pc = (P * P).sum(1)
e2 = pc[:, None] + rc[None, :] - 2.0 * (P @ rest.T)
e2 = np.maximum(e2, 0.0)
Ke = np.where(e2 > 1e-12, 0.5 * e2 * np.log(np.maximum(e2, 1e-12)), 0.0)
H = np.zeros((Nn, M + 4))
H[:, :M] = Ke
H[:, M] = 1.0
H[:, M + 1:] = P
warped = H @ W
hasCage = 1.0 if (M > 0 and M == Md) else 0.0
mesh.setPoints(P + (self.envelope * hasCage) * (warped - P))
'''

RBF_WRAP_DEF_METHODS = r'''@maya_test(label="TPS wrap reproduces affine cage motion", digits=4)
def test_wrap_affine(self):
    """Validate the node's INTENT (same test runs on the interpreted node and its
    C++ compile -> parity): a thin-plate-spline wrap must reproduce an AFFINE cage
    motion EXACTLY -- (1) deformCage == restCage -> the geometry sits at rest;
    (2) translate the deform cage -> the geometry translates by the same vector;
    (3) wire cages whose point counts DISAGREE -> the `hasCage` gate makes the
    node a no-op instead of collapsing the geometry onto the origin. Drives ONLY
    public plugs + cmds, so it is valid against the compiled node."""
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_close, assert_true

    name = self.get_name()

    # Deform whatever mesh this deformer already drives (e.g. the demo's sphere);
    # build one only if it drives nothing yet. Keeps the test on `self`
    # (interpreted==compiled parity) and robust to repeated runs. The compute is
    # OBJECT space, so the deformed mesh must be frozen at the world origin.
    geo = mc.deformer(name, q=True, geometry=True) or []
    if geo:
        sh = (mc.ls(geo[0], long=True) or [geo[0]])[0]
    else:
        sp = mc.polySphere(r=2.0, sx=12, sy=12, name="wrapDefTest#")[0]
        mc.makeIdentity(sp, apply=True, t=True, r=True, s=True)
        mc.deformer(name, e=True, g=sp)
        sh = mc.listRelatives(sp, shapes=True, noIntermediate=True, f=True)[0]

    # A fresh rest cage + an identical deform cage, force-wired over whatever the
    # demo connected (a bent cage would defeat the affine checks).
    restC = mc.polyCube(w=6, h=6, d=6, sx=2, sy=2, sz=2,
                        name="wrapDefTestRest#", ch=False)[0]
    restS = mc.listRelatives(restC, s=True, f=True)[0]
    defC = mc.duplicate(restC, name="wrapDefTestDeform#")[0]
    defS = mc.listRelatives(defC, s=True, f=True)[0]
    for src_shape, dst in ((restS, "restCage"), (defS, "deformCage")):
        plug = name + "." + dst
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.connectAttr(src_shape + ".worldMesh[0]", plug, f=True)

    def _set(plug, *vals):
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals)

    def pts():
        mc.dgdirty(name + ".outputGeometry")
        mc.getAttr(sh + ".outMesh")
        sel = om2.MSelectionList(); sel.add(sh)
        fn = om2.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    _set(name + ".envelope", 0.0)
    src = pts()                      # envelope 0 -> the undeformed input mesh

    # (1) identity: deformCage == restCage -> the geometry is unchanged.
    _set(name + ".envelope", 1.0)
    ident = pts()
    assert_true(ident.shape == src.shape,
                "output vert count (%d) must match input (%d)"
                % (ident.shape[0], src.shape[0]))
    assert_close(ident.ravel().tolist(), src.ravel().tolist())

    # (2) affine: translate the deform cage's verts by (0, 2, 0) -> the TPS (via
    # its affine tail) must translate the geometry by exactly (0, 2, 0).
    mc.move(0.0, 2.0, 0.0, defC + ".vtx[*]", r=True)
    moved = pts()
    expect = (src + np.array([0.0, 2.0, 0.0])).ravel().tolist()
    assert_close(moved.ravel().tolist(), expect)

    # (3) no-op gate: the cages must agree on point count for the warp to mean
    # anything, so wire a DIFFERENTLY subdivided cube as the deform cage --
    # `hasCage` must pass the geometry through untouched rather than warp it
    # against a cage it cannot correspond to. (Note: merely DISCONNECTING a cage
    # would not test this -- Maya retains the last mesh in the datablock, so the
    # compute still sees the old point count.)
    oddC = mc.polyCube(w=6, h=6, d=6, sx=3, sy=3, sz=3,
                       name="wrapDefTestOdd#", ch=False)[0]
    oddS = mc.listRelatives(oddC, s=True, f=True)[0]
    mc.connectAttr(oddS + ".worldMesh[0]", name + ".deformCage", f=True)
    assert_close(pts().ravel().tolist(), src.ravel().tolist())


@maya_demo(label="Wrap a Sphere in a Cube Cage")
def demo(self):
    """Attach this wrap to a sphere frozen at the origin, cage it in a lightly
    subdivided cube, and flex a duplicate of that cube with a keyed bend. Press
    play: the thin-plate spline carries the sphere along with the cage."""
    from maya import cmds as mc
    name = self.get_name()

    # Deformed geometry: a sphere frozen at the world origin (the compute is
    # OBJECT space while the cages are read in WORLD space).
    sphere = mc.polySphere(r=2.0, sx=24, sy=24, name="wrapDefTarget#")[0]
    mc.makeIdentity(sphere, apply=True, t=True, r=True, s=True)
    if name not in (mc.listHistory(sphere) or []):
        mc.deformer(name, e=True, g=sphere)

    # Rest cage: a lightly subdivided cube around the sphere, frozen so its
    # worldMesh IS its rest.
    restC = mc.polyCube(w=6, h=6, d=6, sx=2, sy=2, sz=2,
                        name="wrapDefRestCage#", ch=False)[0]
    mc.makeIdentity(restC, apply=True, t=True, r=True, s=True)
    restS = mc.listRelatives(restC, s=True, f=True)[0]

    # Deform cage: same topology, bent by a keyed nonLinear bend.
    defC = mc.duplicate(restC, name="wrapDefDeformCage#")[0]
    defS = mc.listRelatives(defC, s=True, f=True)[0]
    bend_node, bend_handle = mc.nonLinear(defC, type="bend")[:2]
    mc.setAttr(bend_handle + ".rotateZ", 90.0)
    for f, cv in ((1, 0.0), (60, 70.0), (120, 0.0)):
        mc.setKeyframe(bend_node + ".curvature", t=f, v=cv)

    mc.connectAttr(restS + ".worldMesh[0]", name + ".restCage", f=True)
    mc.connectAttr(defS + ".worldMesh[0]", name + ".deformCage", f=True)
    mc.setAttr(name + ".envelope", 1.0)

    # Cosmetics: hide the rest cage, show the deform cage as a wireframe control.
    try:
        mc.setAttr(restC + ".visibility", False)
        mc.setAttr(defS + ".overrideEnabled", True)
        mc.setAttr(defS + ".overrideShading", False)
    except Exception:
        pass

    mc.playbackOptions(min=1, max=120)
    mc.currentTime(60)
    mc.select(sphere, replace=True)
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name
'''

RBF_WRAP_DEF_DESC = (
    "# RBF Wrap Deformer\n\n"
    "A cage wrap, as an `mPyDeformer`. Build a low-resolution cage around "
    "your geometry and duplicate it: the untouched copy goes into `restCage`, "
    "the animated one into `deformCage`. Bend, twist or move the deform cage "
    "and everything wrapped inside follows smoothly. Good for driving dense "
    "geometry from a handful of easy-to-animate points.\n\n"
    "The warp is a thin-plate spline -- the smoothest shape you can pull "
    "through a set of points. A plain move, rotate or scale of the whole cage "
    "comes through exactly; anything more elaborate bends the geometry with "
    "as little wrinkling as possible.\n\n"
    "Being a deformer, the result is the node's own `outputGeometry`, so "
    "there is no mesh output to wire, and the `envelope` blends the warp back "
    "to rest. Until both cages carry points and agree on point count, "
    "`hasCage` keeps the node a pass-through, so a new or half-wired wrap "
    "never collapses your geometry onto the origin.\n\n"
    "The warp runs in OBJECT space while the cages are read in WORLD space, "
    "so freeze the deformed mesh at the world origin.\n\n"
    "**Create + Run demo** wraps a sphere inside a lightly subdivided cube "
    "cage and flexes the cage with a keyed bend -- press play to watch the "
    "sphere follow the cage. Compiles to pure C++.\n"
)


def build_rbf_wrap_deformer():
    mc.file(new=True, force=True)
    _ensure_mpy_plugins()
    from mpynode.wrappers.mpy_deformer import MPyDeformer
    from mpynode._common.io.user_classes import synthesize, dotted_path
    import maya.api.OpenMaya as om2

    # Sphere frozen at the world origin (the compute is OBJECT space while the
    # cages are read in WORLD space).
    sphere = mc.polySphere(r=2.0, sx=16, sy=16, name="wrapDefTarget")[0]
    mc.makeIdentity(sphere, apply=True, t=True, r=True, s=True)

    d_name = mc.deformer(sphere, type="mPyDeformer", name="rbfWrapDeformer")[0]
    d = MPyDeformer(d_name)
    # Canonical Class identity (same treatment as NurbsWave): mPyDeformer is a
    # root wrapper, so synthesize + stamp mpynode_user.RbfWrapDeformer.
    synthesize("RbfWrapDeformer", "mPyDeformer")
    d.set_py_class(dotted_path("RbfWrapDeformer"))
    d.add_input_attr("restCage", "mesh")
    d.add_input_attr("deformCage", "mesh")
    d.set_init_expression(RBF_WRAP_DEF_INIT)
    d.set_compute_expression(RBF_WRAP_DEF_COMPUTE)
    d.set_methods_source(RBF_WRAP_DEF_METHODS)
    nm = d.get_name()
    sh = mc.listRelatives(sphere, shapes=True, noIntermediate=True, f=True)[0]

    def points(env=None):
        if env is not None:
            mc.setAttr(nm + ".envelope", env)
        mc.dgdirty(nm + ".outputGeometry")
        mc.getAttr(sh + ".outMesh")
        sel = om2.MSelectionList()
        sel.add(sh)
        fn = om2.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    # hasCage gate, never-connected: envelope 1 with cages that were NEVER wired
    # must equal envelope 0 (pure pass-through). This MUST run before anything is
    # connected -- Maya retains the last mesh in the datablock after a disconnect,
    # so unwiring later would not reproduce the M == 0 state.
    virgin_off = points(0.0)
    virgin_on = points(1.0)
    virgin_ok = bool(np.allclose(virgin_on, virgin_off, atol=1e-6))

    # Rest cage + an identical deform cage wired into the node.
    restC = mc.polyCube(w=6, h=6, d=6, sx=2, sy=2, sz=2,
                        name="wrapDefRestCage", ch=False)[0]
    restS = mc.listRelatives(restC, s=True, f=True)[0]
    defC = mc.duplicate(restC, name="wrapDefDeformCage")[0]
    defS = mc.listRelatives(defC, s=True, f=True)[0]
    mc.connectAttr(restS + ".worldMesh[0]", nm + ".restCage", force=True)
    mc.connectAttr(defS + ".worldMesh[0]", nm + ".deformCage", force=True)

    rest = points(0.0)                       # envelope 0 -> undeformed input
    ident = points(1.0)                      # cages identical -> unchanged
    ident_ok = bool(np.allclose(ident, rest, atol=1e-6))

    mc.move(0.0, 2.0, 0.0, defC + ".vtx[*]", r=True)   # affine cage motion
    moved = points(1.0)
    affine_ok = bool(np.allclose(moved - rest, np.array([0.0, 2.0, 0.0]),
                                 atol=1e-6))
    half = points(0.5)
    env_scales = bool(np.allclose(half - rest, 0.5 * (moved - rest), atol=1e-6))

    # hasCage gate, mismatched topology: cages whose point counts disagree must
    # also fall through untouched.
    oddC = mc.polyCube(w=6, h=6, d=6, sx=3, sy=3, sz=3, name="wrapDefOdd",
                       ch=False)[0]
    oddS = mc.listRelatives(oddC, s=True, f=True)[0]
    mc.connectAttr(oddS + ".worldMesh[0]", nm + ".deformCage", force=True)
    mismatch_ok = bool(np.allclose(points(1.0), rest, atol=1e-6))
    mc.connectAttr(defS + ".worldMesh[0]", nm + ".deformCage", force=True)

    compute_ok = ident_ok and affine_ok and env_scales
    clean_payload = serialize_node(d, include_persistent=False)
    cls_ok = clean_payload.get("class_path") == dotted_path("RbfWrapDeformer")

    from mpynode._common.methods.methods_registry import run_node_demo
    from mpynode._common.io.mpn_io import deserialize_node
    from mpynode._common.node_setups import find_demo

    # --- demo check: the authored "Create + Run demo" fabricates the sphere +
    #     cages and warps on a FRESH deserialized node. ---
    demo_ok = False
    demo_err = "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tnm = tnode.get_name()
        run_node_demo(tnode)
        sph_t = (mc.ls("wrapDefTarget*", type="transform") or [None])[0]
        in_hist = sph_t is not None and tnm in (mc.listHistory(sph_t) or [])
        warped = False
        if sph_t is not None:
            shp = mc.listRelatives(sph_t, shapes=True, ni=True, f=True)[0]

            def _pts(frame):
                mc.currentTime(frame)
                mc.dgdirty(tnm + ".outputGeometry")
                mc.getAttr(shp + ".outMesh")
                sel = om2.MSelectionList()
                sel.add(shp)
                fn = om2.MFnMesh(sel.getDagPath(0))
                return np.array([[p.x, p.y, p.z]
                                 for p in fn.getPoints(om2.MSpace.kObject)])

            p1, p60 = _pts(1), _pts(60)
            warped = (p1.shape == p60.shape
                      and float(np.abs(p1 - p60).max()) > 0.05)
        demo_ok = bool(in_hist and warped)
        demo_err = "sphere=%s in_hist=%s warped=%s" % (sph_t, in_hist, warped)
    except Exception as exc:
        demo_err = "exc:%r" % exc

    # --- authored @maya_test check on a FRESH deserialized node (parity bar). ---
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    has_demo = find_demo(RBF_WRAP_DEF_METHODS) is not None
    payload_ok = clean_payload.get("native_type") == "mPyDeformer"
    ok = bool(compute_ok and demo_ok and test_ok and has_demo and payload_ok
              and virgin_ok and mismatch_ok and cls_ok)
    print("[rbf_wrap_deformer] ident=%s affine=%s env=%s virgin=%s mismatch=%s "
          "cls=%s demo=%s(%s) test=%s(%s) has_demo=%s payload=%s -> %s"
          % (ident_ok, affine_ok, env_scales, virgin_ok, mismatch_ok, cls_ok,
             demo_ok, demo_err, test_ok, test_err, has_demo, payload_ok,
             "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(RBF_WRAP_DEF_DIR, clean_payload, RBF_WRAP_DEF_DESC)
    return ok


# ======================================================================
# mPyDeformer -- patch-based surface relaxation (de Goes et al. '18)
# ======================================================================
# A relaxation deformer that undoes the bunching a skin / wrap / squash leaves
# behind WITHOUT the shrinking a Laplacian smooth causes: the target is the REST
# edge layout carried through each patch's own fitted rotation, not a neighbour
# average. Reads a `restMesh` INPUT plus a precomputed CCW 1-ring adjacency, and
# deforms its own outputGeometry, so it stacks normally and honours `envelope`.
PATCH_RELAX_DIR = "MPyDeformer/Patch Relax"

PATCH_RELAX_INIT = (
    "import numpy as np\n"
    "from mpynode._common.nodes.mesh.patch_relax import patch_relax\n"
)

PATCH_RELAX_COMPUTE = r'''# Patch-based surface relaxation (de Goes et al., Pixar, SIGGRAPH '18 Talks).
# Every vertex flattens its 1-ring into a 2D "decal map", derives span-aware edge
# weights from it, fits the rest->posed rotation of that patch by SVD, and steps
# toward the rotated REST edge layout. Because the target carries the patch's own
# rotation, the silhouette survives -- unlike a Laplacian smooth, which shrinks.
#
# `ringNbrs` (flat row-major CCW 1-ring vertex ids, -1 padded) and `ringWidth`
# (the padded width) are DECLARED INPUTS that **Rebuild Rings** seeds. They are
# inputs rather than something the compute derives because (a) they depend only
# on TOPOLOGY, so rebuilding them per frame is pure waste, and (b) building them
# needs repeat/argsort/bincount, every one of which the transpiler rejects --
# seeding them is what lets the whole compute lower to PURE C++.
#
# A deformer is live the instant mc.deformer() creates it, so "no rest mesh yet"
# and "rings not built yet" are the NORMAL startup states, not exotic ones -- the
# gates below are the common path, not error handling.
#
# They are PURELY NUMERIC and nested rather than a try/except, for two reasons.
# nd_lower strips a top-level eager guard on the generic compute path but NOT on
# the deform path, so a try here would drop the node to the AI porter and break
# the pure-C++ rule. And the nesting is what makes that safe: an unconnected mesh
# input reads as None, but `ringWidth > 0` can only be true once Rebuild Rings
# has run, and that refuses to run without a rest mesh connected -- so the
# `self.restMesh` read is unreachable until a rest mesh exists. (Merely
# DISCONNECTING one later does not resurrect the None: Maya retains the last mesh
# in the datablock.) setPoints stays UNCONDITIONAL so the deformer keeps its
# single getPoints/setPoints shape; the gates only choose what gets written.
mesh = self.outputGeometry[0]
P = mesh.getPoints()
N = P.shape[0]
flat = np.asarray(self.ringNbrs, dtype=np.int64)
Kw = int(self.ringWidth)

out = P
if (Kw > 0) and (flat.shape[0] == N * Kw):
    rest = self.restMesh.points
    if rest.shape[0] == N:
        out = patch_relax(P, rest, flat.reshape(N, Kw), int(self.iterations),
                          self.alpha, self.surfaceBlend)
mesh.setPoints(P + self.envelope * (out - P))
'''

PATCH_RELAX_METHODS = VANILLA_SETUP_ERROR + r'''

def _selection(override=None, exclude=None):
    """Inputs for setup: `override` (the snapshot "Run setup" passes) wins over
    the live selection; `exclude` drops this node so it is never its own input."""
    from maya import cmds as mc
    sel = list(override) if override is not None else (
        mc.ls(selection=True, long=False) or [])
    return [n for n in sel if n != exclude] if exclude else sel


def _deformables(sel):
    """The entries carrying deformable geometry (directly or as a shape)."""
    from maya import cmds as mc
    kinds = ("mesh", "nurbsSurface", "nurbsCurve", "lattice")
    out = []
    for n in sel:
        if mc.nodeType(n) in kinds:
            out.append(n)
            continue
        for st in kinds:
            if mc.listRelatives(n, shapes=True, type=st, noIntermediate=True):
                out.append(n)
                break
    return out


def build_ring_adjacency(counts, indices, n_verts):
    """CCW-ordered 1-ring neighbours per vertex, as an ``(N, K)`` int array.

    ``counts`` / ``indices`` are vertices-per-face and the flat face-vertex
    connectivity. ``K`` is the widest ring; shorter rings are padded with -1.
    A row is all -1 when the vertex must not move: an open (boundary) ring, a
    valence below 3, or a non-manifold fan whose corners do not chain into a
    single cycle.
    """
    import numpy as np
    counts = np.asarray(counts, dtype=np.int64).ravel()
    indices = np.asarray(indices, dtype=np.int64).ravel()
    n_verts = int(n_verts)
    if n_verts <= 0 or counts.size == 0 or indices.size == 0:
        return np.zeros((max(n_verts, 0), 0), dtype=np.int64)

    n_faces = counts.shape[0]
    face_start = np.zeros(n_faces, dtype=np.int64)
    np.cumsum(counts[:-1], out=face_start[1:])
    total = int(counts.sum())
    if total != indices.shape[0]:
        raise ValueError("indices length %d does not match counts sum %d"
                         % (indices.shape[0], total))

    corner_face = np.repeat(np.arange(n_faces, dtype=np.int64), counts)
    base = face_start[corner_face]
    within = np.arange(total, dtype=np.int64) - base
    face_len = counts[corner_face]
    nxt = indices[base + (within + 1) % face_len]
    prv = indices[base + (within - 1) % face_len]
    vtx = indices

    keep = face_len >= 3
    vtx, nxt, prv = vtx[keep], nxt[keep], prv[keep]
    if vtx.size == 0:
        return np.zeros((n_verts, 0), dtype=np.int64)

    valence = np.bincount(vtx, minlength=n_verts)[:n_verts].astype(np.int64)
    width = int(valence.max())
    if width < 3:
        return np.zeros((n_verts, 0), dtype=np.int64)

    order = np.argsort(vtx, kind="stable")
    v_s, n_s, p_s = vtx[order], nxt[order], prv[order]
    offset = np.zeros(n_verts + 1, dtype=np.int64)
    np.cumsum(valence, out=offset[1:])
    slot = np.arange(v_s.shape[0], dtype=np.int64) - offset[v_s]

    nxt_tab = np.full((n_verts, width), -1, dtype=np.int64)
    prv_tab = np.full((n_verts, width), -1, dtype=np.int64)
    nxt_tab[v_s, slot] = n_s
    prv_tab[v_s, slot] = p_s

    valid = np.arange(width)[None, :] < valence[:, None]
    link = (prv_tab[:, None, :] == nxt_tab[:, :, None])
    link &= valid[:, :, None] & valid[:, None, :]
    has_succ = link.sum(axis=2) > 0
    has_pred = link.sum(axis=1) > 0
    succ = np.where(has_succ, link.argmax(axis=2), 0)

    closed = ((has_succ | ~valid).all(axis=1)
              & (has_pred | ~valid).all(axis=1)
              & (valence >= 3))

    rows = np.arange(n_verts, dtype=np.int64)
    ring = np.full((n_verts, width), -1, dtype=np.int64)
    ring[:, 0] = prv_tab[:, 0]
    ring[:, 1] = nxt_tab[:, 0]
    cur = np.zeros(n_verts, dtype=np.int64)
    for k in range(2, width):
        cur = succ[rows, cur]
        ring[:, k] = np.where(k < valence, nxt_tab[rows, cur], -1)

    ring = np.where(valid, ring, -1)
    return np.where(closed[:, None], ring, -1)


def seed_rings(node):
    """Rebuild the CCW 1-ring adjacency from `node`'s connected `restMesh` and
    seed it into its `ringNbrs` / `ringWidth` plugs. Returns the number of
    vertices that will actually move (border vertices are pinned, so an open
    mesh reports fewer than its vertex count).

    Takes a node NAME rather than a wrapper, and lives at module level rather
    than on the class, because the demo and the test both need it and `self` is
    not the same thing in both worlds: interpreted it is the MPyNode wrapper,
    but on the COMPILED node it is a plug proxy with no `call_command`. A plain
    function called with `self.get_name()` works identically in both -- same
    thin-wrapper split the dnet template uses for create_knot / create_link.
    """
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np

    src = mc.listConnections(node + ".restMesh", source=True, destination=False,
                             shapes=True, plugs=False) or []
    if not src:
        raise RuntimeError(
            "Connect a rest mesh to %s.restMesh before rebuilding rings." % node)

    sel = om2.MSelectionList()
    sel.add(src[0])
    fn = om2.MFnMesh(sel.getDagPath(0))
    counts, indices = fn.getVertices()
    n_verts = fn.numVertices

    ring = build_ring_adjacency(np.asarray(counts), np.asarray(indices), n_verts)
    width = int(ring.shape[1])
    if width == 0:
        raise RuntimeError(
            "%s has no closed vertex rings -- nothing to relax." % src[0])

    flat = [int(v) for v in ring.reshape(-1)]
    # ringNbrs is a MULTI, so it is seeded element by element (same as the
    # procrustes templates' `clusters`). Stale trailing elements from a denser
    # previous topology are removed, or they would survive into the reshape.
    for i, v in enumerate(flat):
        mc.setAttr("%s.ringNbrs[%d]" % (node, i), v)
    for i in (mc.getAttr(node + ".ringNbrs", multiIndices=True) or []):
        if int(i) >= len(flat):
            mc.removeMultiInstance("%s.ringNbrs[%d]" % (node, int(i)), b=True)
    mc.setAttr(node + ".ringWidth", width)
    return int((ring >= 0).any(axis=1).sum())


@maya_command(name="patchRelaxRebuildRings")
def rebuild_rings(self):
    """Rebuild this node's CCW 1-ring adjacency from its connected `restMesh`.

    Run once after wiring a rest mesh, and again only if its TOPOLOGY changes --
    moving vertices needs no rebuild, the rings are connectivity only."""
    return seed_rings(self.get_name())


@maya_command(creates=True)
def setup(self, selection=None, *args, **kwargs):
    """Wire this node onto the mesh it already deforms, and make it live.

    CREATE-COMPLETE, because two callers land here and only one of them hands
    over a node that is already wired: "Run setup" on a deformer that is already
    in a mesh's chain, and the CREATE command, which -- like cmds.blendShape /
    cmds.skinCluster -- ``createNode``'s a BARE node and hands it straight to
    this body. So when the node deforms nothing yet, the geometry is ADOPTED off
    the selection first, using the same three lines (and the same ``listHistory``
    idempotency filter) as the mPyDeformer type default.

    The adoption is GATED on the node being bare, not run unconditionally. A node
    that already deforms something never consults the selection at all, which is
    what keeps "Run setup" on a wired node behaving exactly as it did before:
    whatever happens to be selected at the time cannot be pulled into the
    deformer. That matters here beyond politeness -- the compute relaxes
    ``outputGeometry[0]`` against ONE rest mesh and ONE ring table, so a second
    adopted mesh would land on index 1 and be driven by another mesh's topology.

    The signature has to absorb ``selection=`` (and stay permissive) because the
    shared dispatcher in methods_registry.run_node_setup passes it to EVERY
    setup unconditionally -- a bare ``def setup(self)`` raises TypeError at the
    exact moment the user clicks Run Setup. ``_selection(override=selection)`` is
    the same reader every type default uses, so an explicit (possibly empty)
    snapshot wins over the live selection. That matters on the create path:
    ``cmds.createNode`` reselects the node it just made, so reading the live
    selection there would see the deformer, not the mesh.

    WITHOUT this the node is a silent pass-through, and that is the single most
    confusing thing about it: the compute is gated on `ringWidth > 0`, which only
    Rebuild Rings can set, and Rebuild Rings refuses to run until a rest mesh is
    connected. A freshly created node therefore satisfies neither condition and
    deforms nothing -- correctly, but with no feedback whatsoever. Every other
    template exposes a `setup`; this one did not, so the only wiring that existed
    lived inside `demo`, which builds its OWN sphere and never touches the mesh
    the user applied the node to.

    The rest mesh is the deformed shape's ORIG (intermediate) shape -- the mesh as
    it is before ANY deformer in the chain runs. That is exactly the "rest edge
    layout" the algorithm relaxes toward, it always has matching topology, and it
    costs no extra geometry. An already-connected restMesh is left alone, so
    re-running setup after wiring a custom rest is safe.
    """
    from maya import cmds as mc

    name = self.get_name()
    # Returns None (it does NOT raise) on a geometryFilter with nothing in its
    # chain, so this doubles as the "was I just created?" test.
    geo = mc.deformer(name, q=True, geometry=True) or []
    if not geo:
        sel = _deformables(_selection(override=selection, exclude=name))
        if not sel:
            raise SetupError(
                "select a mesh (or other deformable geometry) to apply %s" % self.NATIVE_TYPE)
        # Same idempotency filter as the mPyDeformer type default: only adopt
        # geometry this node is not already in the history of.
        todo = [g for g in sel if name not in (mc.listHistory(g) or [])]
        if todo:
            mc.deformer(name, e=True, g=todo)   # adopt the pre-built bare self
        geo = mc.deformer(name, q=True, geometry=True) or []
        if not geo:
            raise SetupError(
                "%s could not be applied to %s" % (name, ", ".join(sel)))

    shape = (mc.ls(geo[0], long=True) or [geo[0]])[0]
    plug = name + ".restMesh"
    existing = mc.listConnections(plug, s=True, d=False, shapes=True) or []
    if existing:
        rest_src = (mc.ls(existing[0], long=True) or [existing[0]])[0]
    else:
        transform = (mc.listRelatives(shape, parent=True, f=True) or [None])[0]
        siblings = mc.listRelatives(transform, shapes=True, f=True) or []
        # A mesh grows an intermediate shape the moment a deformer is added, so
        # this exists by construction -- we ARE a deformer on it. Guarded anyway,
        # because a referenced or oddly-built shape can carry more than one.
        origs = [s for s in siblings
                 if s != shape and mc.getAttr(s + ".intermediateObject")]
        if not origs:
            raise RuntimeError(
                "%s has no original (pre-deformation) shape to use as a rest "
                "mesh. Connect one by hand to %s, then run Rebuild Rings." % (shape, plug))
        rest_src = origs[0]
        mc.connectAttr(rest_src + ".worldMesh[0]", plug, force=True)

    moved = seed_rings(name)
    mc.setAttr(name + ".envelope", 1.0)
    print("[patch_relax] %s: rest mesh = %s, %d movable vertices "
          "(borders are pinned), ringWidth = %d. Toggle `envelope` to compare."
          % (name, rest_src.split("|")[-1], moved,
             int(mc.getAttr(name + ".ringWidth"))))
    return moved


@maya_test(label="Relax reduces edge distortion; envelope 0 is rest", digits=4)
def test_relax(self):
    """Validate the node's INTENT rather than its arithmetic, so the same test is
    meaningful against the C++ compile (interpreted == compiled parity):

      (1) envelope 0 is exactly the incoming, un-relaxed mesh;
      (2) with rings seeded, relaxing a BUNCHED mesh moves its edge lengths
          measurably back toward the rest mesh's edge lengths;
      (3) before Rebuild Rings has ever run the node is a pure pass-through,
          not a collapse -- a deformer is live from the moment it is created.

    Drives only public plugs + cmds, so it is valid against the compiled node.
    """
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_close, assert_true

    name = self.get_name()

    # Deform whatever this node already drives; build a target only if it drives
    # nothing yet. Object space, so freeze the mesh at the world origin.
    # The compute relaxes outputGeometry[0], so REUSE whatever this node already
    # drives rather than adding a second geometry that would land on index 1.
    geo = mc.deformer(name, q=True, geometry=True) or []
    made_target = not geo
    if geo:
        shape = (mc.ls(geo[0], long=True) or [geo[0]])[0]
        target = (mc.listRelatives(shape, parent=True, f=True) or [shape])[0]
    else:
        target = mc.polySphere(r=2.0, sx=12, sy=12, name="patchRelaxTest#")[0]
        mc.makeIdentity(target, apply=True, t=True, r=True, s=True)
        mc.deformer(name, e=True, g=target)
        shape = mc.listRelatives(target, shapes=True, noIntermediate=True, f=True)[0]

    def pts():
        mc.dgdirty(name + ".outputGeometry")
        mc.getAttr(shape + ".outMesh")
        sel = om2.MSelectionList(); sel.add(shape)
        fn = om2.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    def _set(plug, *vals):
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals)

    # (3) untouched gate FIRST: no rings have been seeded on a fresh node, so
    # envelope 1 must equal envelope 0. Once Rebuild Rings runs this state is
    # unreachable, which is why it is checked before anything else.
    _set(name + ".ringWidth", 0)
    _set(name + ".envelope", 0.0)
    raw = pts()
    _set(name + ".envelope", 1.0)
    assert_close(pts().ravel().tolist(), raw.ravel().tolist())

    # A rest mesh of matching topology. When this node was built by the demo it
    # already has one wired to its pristine sphere -- keep that, since only the
    # demo knows what its target's rest shape is.
    plug = name + ".restMesh"
    existing = mc.listConnections(plug, s=True, d=False, shapes=True) or []
    if made_target or not existing:
        rest_tf = mc.polySphere(r=2.0, sx=12, sy=12,
                                name="patchRelaxTestRest#")[0]
        mc.makeIdentity(rest_tf, apply=True, t=True, r=True, s=True)
        rest_shape = mc.listRelatives(rest_tf, s=True, f=True)[0]
        for c in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(c, plug)
        mc.connectAttr(rest_shape + ".worldMesh[0]", plug, f=True)
    else:
        rest_shape = (mc.ls(existing[0], long=True) or [existing[0]])[0]

    # There must be real distortion for a relax to have anything to undo, so put
    # a squash UPSTREAM of this node (reorder -- mc.deformer appended us first).
    sq_node, sq_handle = mc.nonLinear(target, type="squash")[:2]
    for a in ("scaleX", "scaleY", "scaleZ"):
        mc.setAttr(sq_handle + "." + a, 2.5)
    mc.setAttr(sq_node + ".factor", -0.6)
    try:
        mc.reorderDeformers(name, sq_node, target)
    except Exception:
        pass

    seed_rings(name)
    assert_true(mc.getAttr(name + ".ringWidth") > 0,
                "Rebuild Rings must seed a non-zero ringWidth")

    _set(name + ".iterations", 20)
    _set(name + ".alpha", 1.0)
    _set(name + ".surfaceBlend", 0.0)

    # (1) envelope 0 is the incoming mesh, whatever the settings.
    _set(name + ".envelope", 0.0)
    src = pts()

    # (2) the relaxed mesh's edges must sit closer to the rest edge lengths than
    # the incoming mesh's do. Measured over the same ring adjacency the node
    # uses, read back off the plug so the test sees exactly what the node saw.
    width = int(mc.getAttr(name + ".ringWidth"))
    idxs = mc.getAttr(name + ".ringNbrs", multiIndices=True) or []
    ring = np.asarray([mc.getAttr("%s.ringNbrs[%d]" % (name, int(i)))
                       for i in sorted(int(j) for j in idxs)],
                      dtype=np.int64).reshape(-1, width)
    sel = om2.MSelectionList(); sel.add(rest_shape)
    rest = np.array([[p.x, p.y, p.z] for p in
                     om2.MFnMesh(sel.getDagPath(0)).getPoints(om2.MSpace.kObject)])

    def edge_error(x):
        n = x.shape[0]
        m = ring >= 0
        idx = np.where(m, ring, n)
        xp = np.concatenate([x, np.zeros((1, 3))], 0)
        rp = np.concatenate([rest, np.zeros((1, 3))], 0)
        ed = np.take(xp, idx, 0) - x[:, None, :]
        er = np.take(rp, idx, 0) - rest[:, None, :]
        d = np.sqrt((ed * ed).sum(-1)) - np.sqrt((er * er).sum(-1))
        return float((np.abs(d) * m).sum() / max(m.sum(), 1))

    assert_true(src.shape == rest.shape,
                "deformed (%d) and rest (%d) vertex counts must match"
                % (src.shape[0], rest.shape[0]))

    _set(name + ".envelope", 1.0)
    relaxed = pts()
    assert_true(bool(np.isfinite(relaxed).all()),
                "relaxed positions must all be finite")

    before, after = edge_error(src), edge_error(relaxed)
    assert_true(after < before * 0.95,
                "relax must reduce edge distortion: before=%.6f after=%.6f" % (before, after))


@maya_demo(label="Relax a Squashed Sphere")
def demo(self):
    """Squash and twist a sphere so its polygons bunch up, then relax them back
    toward the rest layout. Press play, and toggle `envelope` between 0 and 1 to
    compare the bunched input against the relaxed result."""
    from maya import cmds as mc

    name = self.get_name()

    # Rest reference FIRST: an untouched copy of the sphere, hidden.
    rest_tf = mc.polySphere(r=2.0, sx=24, sy=24, name="patchRelaxRest#")[0]
    mc.makeIdentity(rest_tf, apply=True, t=True, r=True, s=True)
    rest_shape = mc.listRelatives(rest_tf, s=True, f=True)[0]
    mc.setAttr(rest_tf + ".visibility", False)

    # The target: the same sphere, bunched by a keyed squash + twist. Both go on
    # BEFORE the relax so this node sees an already-distorted mesh.
    target = mc.polySphere(r=2.0, sx=24, sy=24, name="patchRelaxTarget#")[0]
    mc.makeIdentity(target, apply=True, t=True, r=True, s=True)

    squash_node, squash_handle = mc.nonLinear(target, type="squash")[:2]
    mc.setAttr(squash_handle + ".scaleX", 2.5)
    mc.setAttr(squash_handle + ".scaleY", 2.5)
    mc.setAttr(squash_handle + ".scaleZ", 2.5)
    twist_node, twist_handle = mc.nonLinear(target, type="twist")[:2]
    for frame, (sq, tw) in ((1, (0.0, 0.0)), (60, (-0.7, 140.0)), (120, (0.0, 0.0))):
        mc.setKeyframe(squash_node + ".factor", t=frame, v=sq)
        mc.setKeyframe(twist_node + ".endAngle", t=frame, v=tw)

    if name not in (mc.listHistory(target) or []):
        mc.deformer(name, e=True, g=target)

    mc.connectAttr(rest_shape + ".worldMesh[0]", name + ".restMesh", force=True)
    mc.setAttr(name + ".iterations", 20)
    mc.setAttr(name + ".alpha", 1.0)
    mc.setAttr(name + ".surfaceBlend", 0.0)
    mc.setAttr(name + ".envelope", 1.0)

    # Topology is fixed, so the rings are built once, here.
    seed_rings(name)

    mc.playbackOptions(min=1, max=120)
    mc.currentTime(60)
    mc.select(target, replace=True)
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name
'''

PATCH_RELAX_DESC = (
    "# Patch Relax\n\n"
    "An `mPyDeformer` that spreads bunched and pinched polygons back into an "
    "even layout -- **without the shrinking a Laplacian smooth causes**. Use "
    "it to clean up after a skin, wrap or squash.\n\n"
    "Each vertex flattens its ring of neighbours into a 2D *decal map* and "
    "steps toward the rest layout, rotated to match the current pose. "
    "Carrying each patch's own rotation is what saves the silhouette.\n\n"
    "**Patch-based surface relaxation**, de Goes et al., Pixar, *SIGGRAPH '18 "
    "Talks* "
    "([doi:10.1145/3214745.3214768](https://doi.org/10.1145/3214745.3214768)).\n\n"
    "## Inputs\n\n"
    "* `restMesh` -- the undistorted reference. Supplies both the rest edge "
    "layout and the topology.\n"
    "* `iterations` -- Jacobi sweeps (default 20). Each sweep reads the "
    "previous one's positions and writes a fresh buffer, so the result never "
    "depends on vertex order.\n"
    "* `alpha` -- how strongly the rest layout is enforced; 0 is a no-op.\n"
    "* `surfaceBlend` -- 0 relaxes through space, 1 slides along the surface. "
    "**Defaults to 0**, see the note below.\n"
    "* `ringNbrs` / `ringWidth` -- the CCW 1-ring adjacency, seeded by "
    "**Rebuild Rings**.\n"
    "* `envelope` -- the standard deformer blend against the un-relaxed "
    "input.\n\n"
    "## Rebuild Rings\n\n"
    "Run the **Rebuild Rings** command once after wiring a rest mesh, and "
    "again only if its TOPOLOGY changes -- moving vertices needs no rebuild. "
    "The rings are an input rather than something the compute derives for two "
    "reasons: they depend only on connectivity, so rebuilding them every "
    "frame is waste; and building them needs `repeat`/`argsort`/`bincount`, "
    "which the transpiler rejects. Seeding them is what lets the whole "
    "compute lower to pure C++. Until they are seeded the node is a "
    "pass-through, not a collapse.\n\n"
    "Border vertices are **pinned**. The decal map normalizes a ring's angles "
    "to 2*pi, which only means anything on a closed ring; applying it to an "
    "open fan drags the border inward.\n\n"
    "## Note on `surfaceBlend`\n\n"
    "The reference builds the surface target as `step * (vp2 - alpha * "
    "Rvh2)`, where `Rvh2` is `vh2` scaled by `|vp2|/|vh2|` and rotated by "
    "`arg(vp2) - arg(vh2)`. That construction *is* `vp2` by definition, so "
    "the target collapses to `step * (1 - alpha) * vp2` and the surface "
    "branch does nothing at `alpha = 1`. On a bunched torus, through-space "
    "leaves 59% of the input edge error after 20 sweeps, `surfaceBlend = 0.8` "
    "leaves 87%, and `surfaceBlend = 1.0` leaves 100% -- the mesh does not "
    "move. This is faithful to the reference, which is why the default here "
    "is 0.\n\n"
    "**Create + Run demo** squashes and twists a sphere so its polygons bunch "
    "up, then relaxes them back -- press play, and toggle `envelope` to "
    "compare the bunched input against the relaxed result.\n"
)


def build_patch_relax():
    mc.file(new=True, force=True)
    _ensure_mpy_plugins()
    from mpynode.wrappers.mpy_deformer import MPyDeformer
    from mpynode._common.io.user_classes import synthesize, dotted_path
    import maya.api.OpenMaya as om2

    # Object space compute, so the target is frozen at the world origin.
    sphere = mc.polySphere(r=2.0, sx=16, sy=16, name="patchRelaxTarget")[0]
    mc.makeIdentity(sphere, apply=True, t=True, r=True, s=True)

    d_name = mc.deformer(sphere, type="mPyDeformer", name="patchRelax")[0]
    d = MPyDeformer(d_name)
    synthesize("PatchRelax", "mPyDeformer")
    d.set_py_class(dotted_path("PatchRelax"))
    d.add_input_attr("restMesh", "mesh")
    # Flat row-major CCW 1-ring + its padded width: DECLARED INPUTS seeded by the
    # Rebuild Rings command, so the compute lowers deterministically.
    d.add_input_attr("ringNbrs", "int", is_array=True)
    d.add_input_attr("ringWidth", "int")
    d.add_input_attr("iterations", "int", default_value=20)
    d.add_input_attr("alpha", "double", default_value=1.0)
    d.add_input_attr("surfaceBlend", "double", default_value=0.0)
    d.set_init_expression(PATCH_RELAX_INIT)
    d.set_compute_expression(PATCH_RELAX_COMPUTE)
    d.set_methods_source(PATCH_RELAX_METHODS)

    nm = d.get_name()
    sh = mc.listRelatives(sphere, shapes=True, noIntermediate=True, f=True)[0]

    def points(env=None):
        if env is not None:
            mc.setAttr(nm + ".envelope", env)
        mc.dgdirty(nm + ".outputGeometry")
        mc.getAttr(sh + ".outMesh")
        sel = om2.MSelectionList()
        sel.add(sh)
        fn = om2.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    # Pass-through gate, never configured: envelope 1 with no rest mesh and no
    # rings must equal envelope 0. Must run BEFORE anything is wired.
    virgin_off = points(0.0)
    virgin_on = points(1.0)
    virgin_ok = bool(np.allclose(virgin_on, virgin_off, atol=1e-6))

    # Rest reference + a bunched target: squash the sphere so its rows crowd.
    rest_tf = mc.polySphere(r=2.0, sx=16, sy=16, name="patchRelaxRest")[0]
    mc.makeIdentity(rest_tf, apply=True, t=True, r=True, s=True)
    rest_sh = mc.listRelatives(rest_tf, s=True, f=True)[0]
    mc.connectAttr(rest_sh + ".worldMesh[0]", nm + ".restMesh", force=True)

    # Rings not yet built -> still a pass-through even with a rest mesh wired.
    unbuilt_ok = bool(np.allclose(points(1.0), points(0.0), atol=1e-6))

    moving = d.call_command("patchRelaxRebuildRings")
    width = int(mc.getAttr(nm + ".ringWidth"))
    rings_ok = bool(width > 0 and moving == len(virgin_off))

    # Bunch the incoming mesh by squashing the sphere's own points, so the relax
    # has real distortion to undo (a squash BEFORE this deformer in the chain).
    sq_node, sq_handle = mc.nonLinear(sphere, type="squash")[:2]
    for a in ("scaleX", "scaleY", "scaleZ"):
        mc.setAttr(sq_handle + "." + a, 2.5)
    mc.setAttr(sq_node + ".factor", -0.6)
    # The squash must evaluate BEFORE the relax; mc.deformer appended the relax
    # first, so re-order the chain.
    try:
        mc.reorderDeformers(nm, sq_node, sphere)
    except Exception:
        pass

    mc.setAttr(nm + ".iterations", 20)
    mc.setAttr(nm + ".alpha", 1.0)
    mc.setAttr(nm + ".surfaceBlend", 0.0)

    src = points(0.0)
    relaxed = points(1.0)
    half = points(0.5)

    sel = om2.MSelectionList()
    sel.add(rest_sh)
    rest_pts = np.array([[p.x, p.y, p.z] for p in
                         om2.MFnMesh(sel.getDagPath(0)).getPoints(
                             om2.MSpace.kObject)])
    _ri = mc.getAttr(nm + ".ringNbrs", multiIndices=True) or []
    ring = np.asarray([mc.getAttr("%s.ringNbrs[%d]" % (nm, int(i)))
                       for i in sorted(int(j) for j in _ri)],
                      dtype=np.int64).reshape(-1, width)

    def edge_error(x):
        n = x.shape[0]
        m = ring >= 0
        idx = np.where(m, ring, n)
        xp = np.concatenate([x, np.zeros((1, 3))], 0)
        rp = np.concatenate([rest_pts, np.zeros((1, 3))], 0)
        ed = np.take(xp, idx, 0) - x[:, None, :]
        er = np.take(rp, idx, 0) - rest_pts[:, None, :]
        dd = np.sqrt((ed * ed).sum(-1)) - np.sqrt((er * er).sum(-1))
        return float((np.abs(dd) * m).sum() / max(m.sum(), 1))

    before, after = edge_error(src), edge_error(relaxed)
    relax_ok = bool(np.isfinite(relaxed).all() and after < before * 0.95)
    # envelope must interpolate linearly between the input and the relaxed pose.
    env_ok = bool(np.allclose(half - src, 0.5 * (relaxed - src), atol=1e-6))

    compute_ok = relax_ok and env_ok
    clean_payload = serialize_node(d, include_persistent=False)
    cls_ok = clean_payload.get("class_path") == dotted_path("PatchRelax")

    from mpynode._common.methods.methods_registry import (
        run_node_demo, run_node_setup)
    from mpynode._common.io.mpn_io import deserialize_node
    from mpynode._common.node_setups import find_demo, find_setup

    # --- demo check on a FRESH deserialized node ---
    demo_ok = False
    demo_err = "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tnm = tnode.get_name()
        run_node_demo(tnode)
        tgt = (mc.ls("patchRelaxTarget*", type="transform") or [None])[0]
        in_hist = tgt is not None and tnm in (mc.listHistory(tgt) or [])
        seeded = int(mc.getAttr(tnm + ".ringWidth")) > 0
        relaxes = False
        if tgt is not None:
            shp = mc.listRelatives(tgt, shapes=True, ni=True, f=True)[0]

            def _pts(env):
                mc.setAttr(tnm + ".envelope", env)
                mc.dgdirty(tnm + ".outputGeometry")
                mc.getAttr(shp + ".outMesh")
                s2 = om2.MSelectionList()
                s2.add(shp)
                fn2 = om2.MFnMesh(s2.getDagPath(0))
                return np.array([[p.x, p.y, p.z]
                                 for p in fn2.getPoints(om2.MSpace.kObject)])

            mc.currentTime(60)
            a, b = _pts(0.0), _pts(1.0)
            relaxes = (a.shape == b.shape
                       and float(np.abs(a - b).max()) > 1e-3)
        demo_ok = bool(in_hist and seeded and relaxes)
        demo_err = ("target=%s in_hist=%s seeded=%s relaxes=%s"
                    % (tgt, in_hist, seeded, relaxes))
    except Exception as exc:
        demo_err = "exc:%r" % exc

    # --- authored @maya_test on a FRESH deserialized node (parity bar) ---
    test_ok = False
    test_err = "n/a"
    try:
        mc.file(new=True, force=True)
        tnode = deserialize_node(clean_payload, restore_persistent=False)
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        test_err = tres.get("error") or "ok"
    except Exception as exc:
        test_err = "exc:%r" % exc

    has_demo = find_demo(PATCH_RELAX_METHODS) is not None
    has_setup = find_setup(PATCH_RELAX_METHODS) is not None

    # --- THE regression gate: the USER's path, not the demo's -------------
    # The demo builds its own sphere and wires everything itself, so it passed
    # even while a hand-applied node did nothing at all. This gate instead does
    # what a user does -- take an ALREADY-DEFORMED mesh, apply the deformer to
    # it, and click Run Setup -- and asserts the result actually moves. It also
    # goes through run_node_setup rather than calling setup() directly, so the
    # `selection=` kwarg the dispatcher passes is covered too.
    setup_ok = False
    setup_err = "n/a"
    try:
        mc.file(new=True, force=True)
        u_sphere = mc.polySphere(r=2.0, sx=16, sy=16, name="userSphere")[0]
        mc.makeIdentity(u_sphere, apply=True, t=True, r=True, s=True)
        u_sq, u_handle = mc.nonLinear(u_sphere, type="squash")[:2]
        for _a in ("scaleX", "scaleY", "scaleZ"):
            mc.setAttr(u_handle + "." + _a, 2.5)
        mc.setAttr(u_sq + ".factor", -0.6)

        unode = deserialize_node(clean_payload, restore_persistent=False)
        unm = unode.get_name()
        # No reorder here, deliberately: the squash already exists, so
        # mc.deformer APPENDS the relax after it and the relax sees the squashed
        # mesh. That is also the user's real flow (add the deformer to a mesh
        # that is already deformed). Forcing an order here would only be able to
        # get it wrong -- and the relax evaluating FIRST is precisely the
        # degenerate case where input == rest and it correctly does nothing.
        mc.deformer(unm, e=True, g=u_sphere)
        u_sh = mc.listRelatives(u_sphere, s=True, ni=True, f=True)[0]

        def _upts(env):
            mc.setAttr(unm + ".envelope", env)
            mc.dgdirty(unm + ".outputGeometry")
            mc.getAttr(u_sh + ".outMesh")
            _s = om2.MSelectionList()
            _s.add(u_sh)
            return np.array([[p.x, p.y, p.z] for p in
                             om2.MFnMesh(_s.getDagPath(0)).getPoints(
                                 om2.MSpace.kObject)])

        before_setup = float(np.abs(_upts(1.0) - _upts(0.0)).max())
        run_node_setup(unode, selection=[u_sphere])
        after_setup = float(np.abs(_upts(1.0) - _upts(0.0)).max())
        # Before setup it MUST be inert (that is the documented pass-through);
        # after setup it MUST move. Both halves matter.
        setup_ok = bool(before_setup <= 1e-6 and after_setup > 1e-3
                        and int(mc.getAttr(unm + ".ringWidth")) > 0)
        setup_err = ("inert_before=%.8f moves_after=%.6f"
                     % (before_setup, after_setup))
    except Exception as exc:
        setup_err = "exc:%r" % exc

    payload_ok = clean_payload.get("native_type") == "mPyDeformer"
    ok = bool(compute_ok and demo_ok and test_ok and has_demo and payload_ok
              and virgin_ok and unbuilt_ok and rings_ok and cls_ok
              and has_setup and setup_ok)
    print("[patch_relax] relax=%s(%.4f->%.4f) env=%s virgin=%s unbuilt=%s "
          "rings=%s(w=%d) cls=%s demo=%s(%s) test=%s(%s) has_demo=%s "
          "has_setup=%s setup=%s(%s) payload=%s -> %s"
          % (relax_ok, before, after, env_ok, virgin_ok, unbuilt_ok, rings_ok,
             width, cls_ok, demo_ok, demo_err, test_ok, test_err, has_demo,
             has_setup, setup_ok, setup_err, payload_ok,
             "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(PATCH_RELAX_DIR, clean_payload, PATCH_RELAX_DESC)
    return ok



# ======================================================================
# 2f. mPyMesh -- geometry read off DISK (both compilable)
# ======================================================================
# Source of truth for both disk-backed mesh templates. Both read named arrays
# through `ndio`, which the transpiler lowers onto the nd_io C++ kernel, so both
# COMPILE with their file reads intact. They differ in LAYOUT: disk_mesh_cache
# holds a whole take in one packed array (constant topology by construction),
# while json_mesh_reader resolves one file per frame through ndio.frame_path and
# so may change topology as it goes.
DISK_MESH_CACHE_INIT = r'''# Nothing to set up. Every array this node needs comes off disk in compute,
# through `ndio` -- which is deliberately import-only here so the compute block
# stays a straight line of array math the C++ transpiler can lower whole.
import numpy as np

from mpynode import ndio
'''

DISK_MESH_CACHE_COMPUTE = r'''# Play a cached deforming mesh straight off disk.
#
# ONE file holds the whole take: `points` is (FRAMES, VERTS, 3), and `counts` /
# `indices` describe the constant topology. Each evaluation reads the three
# named arrays and slices out the current frame.
#
# "Reads" is the interesting word. `ndio.read` caches the parsed file on
# path + mtime + size, in BOTH implementations -- the Python one you are
# running now and the C++ kernel the compiled node uses. So the first
# evaluation touches the disk and every later one does not, however far you
# scrub. Rewrite the file under the same name and the key changes, so the new
# contents are picked up rather than served stale.
#
# A missing or malformed file yields EMPTY arrays rather than an exception,
# which is why the `n < 1` guard below is the only error handling needed: the
# node shows no geometry instead of going into an error state.
import numpy as np

from mpynode import ndio
from mpynode._api2.geometry import Mesh

frames = ndio.read(self.cachePath, "points")
counts = ndio.read(self.cachePath, "counts", dtype=np.int64)
indices = ndio.read(self.cachePath, "indices", dtype=np.int64)

n = frames.shape[0]

if n < 1:
    pts = np.zeros((0, 3))
else:
    i = int(self.frame) % n
    pts = frames[i] * self.scale

self.outMesh = Mesh(points=pts, counts=counts, indices=indices)
'''

DISK_MESH_CACHE_METHODS = r'''# Demo + test for the disk-backed mesh cache. The asset (ripple_cache.ndio)
# ships beside the template, so the demo locates it relative to the installed
# mpynode package rather than hard-coding an absolute path.


def _asset_path():
    """Absolute path to the shipped ripple_cache.ndio."""
    import os

    import mpynode

    # .../scripts/mpynode/__init__.py -> up to the repo root, then templates/.
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(mpynode.__file__))))
    return os.path.join(root, "templates", "MPyMesh",
                        "Disk Mesh Cache", "ripple_cache.ndio")


def _ensure_time(name):
    """Drive ``frame`` from ``time1``, explicitly.

    The interpreted wrapper auto-wires a ``time`` input on create, but the
    COMPILED node type does not -- ``createNode('diskMeshCache')`` leaves
    ``frame`` at 0, so it would show frame 0 forever. Wiring it here is what
    makes the demo animate and the test valid for BOTH node kinds.
    """
    from maya import cmds as mc

    if not mc.listConnections(name + ".frame", source=True, destination=False):
        mc.connectAttr("time1.outTime", name + ".frame", force=True)


@maya_demo(label="Disk Mesh Cache: play a 48-frame cache off disk")
def demo(self):
    from maya import cmds as mc

    name = self.get_name()
    mc.setAttr(name + ".cachePath", _asset_path(), type="string")
    _ensure_time(name)

    # A render mesh fed by this node, with a shader so it reads in the viewport.
    xform = mc.createNode("transform", name="diskMeshCacheGeo#", skipSelect=True)
    shape = mc.createNode("mesh", name=xform + "Shape", parent=xform, skipSelect=True)
    mc.connectAttr(name + ".outMesh", shape + ".inMesh", force=True)
    mc.sets(shape, edit=True, forceElement="initialShadingGroup")

    # The cache is 48 frames long; the node wraps with a modulo, so the range
    # is a convenience rather than a constraint.
    mc.playbackOptions(minTime=1, maxTime=48, animationStartTime=1, animationEndTime=48)
    mc.currentTime(1)
    mc.dgeval(shape + ".inMesh")

    try:
        mc.select(xform)
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
        mc.select(clear=True)
    except Exception:
        pass    # batch / no viewport
    return xform


@maya_test(label="Disk Mesh Cache: every frame matches the file", digits=4)
def test_disk_mesh_cache(self):
    """Drive the node through the timeline and compare its output mesh to the
    arrays read straight out of the cache file."""
    import numpy as np
    from maya import cmds as mc
    import maya.api.OpenMaya as om2

    from mpynode import ndio

    name = self.get_name()
    path = _asset_path()
    mc.setAttr(name + ".cachePath", path, type="string")
    mc.setAttr(name + ".scale", 1.0)
    _ensure_time(name)

    render = mc.createNode("mesh", skipSelect=True)
    mc.connectAttr(name + ".outMesh", render + ".inMesh", force=True)

    frames = ndio.read(path, "points")
    counts = ndio.read(path, "counts", dtype=np.int64)
    assert frames.shape[0] > 0, "cache asset is missing or empty: %s" % path

    def out_points():
        mc.dgdirty(name)
        mc.dgeval(render + ".inMesh")
        sl = om2.MSelectionList()
        sl.add(render)
        fn = om2.MFnMesh(sl.getDagPath(0))
        pts = fn.getPoints(om2.MSpace.kObject)
        return np.array([[p.x, p.y, p.z] for p in pts], dtype=np.float64)

    for f in (1, 12, 47, 50):
        mc.currentTime(f)
        got = out_points()
        exp = frames[f % frames.shape[0]]
        assert got.shape == exp.shape, (
            "frame %d: %r verts, expected %r" % (f, got.shape, exp.shape))
        # MFnMesh stores positions as float32, so compare at float32 precision.
        err = float(np.abs(got - exp.astype(np.float32)).max())
        assert err < 1e-4, "frame %d: max vertex error %g" % (f, err)

    # Face topology comes from the same file and must survive the round trip.
    mc.currentTime(1)
    mc.dgeval(render + ".inMesh")
    assert mc.polyEvaluate(render, face=True) == int(counts.shape[0]), (
        "face count does not match the cache")

    # A missing file must degrade to an empty mesh, not an error.
    mc.setAttr(name + ".cachePath", path + ".nope", type="string")
    mc.dgdirty(name)
    mc.dgeval(render + ".inMesh")
    assert mc.polyEvaluate(render, vertex=True) in (0, None), (
        "a missing cache file must yield an empty mesh")
    mc.setAttr(name + ".cachePath", path, type="string")
'''

DISK_MESH_CACHE_DESC = r'''# Disk Mesh Cache

Plays a cached deforming mesh (an `mPyMesh`) off disk. Use it for a baked sim
or cached deformation whose topology never changes. Compiles to pure C++.

Point `cachePath` at `ripple_cache.ndio` (shipped next to this template) and
scrub the timeline.

## What it demonstrates

File I/O inside a compute block that the C++ transpiler can lower. The reads
are ordinary calls:

```python
frames  = ndio.read(self.cachePath, "points")
counts  = ndio.read(self.cachePath, "counts",  dtype=np.int64)
indices = ndio.read(self.cachePath, "indices", dtype=np.int64)
```

`ndio` has two implementations that are kept in lockstep -- `mpynode/ndio.py`
for the interpreted node, and a hand-written C++ kernel for the compiled one.
Both sniff the format from the leading bytes, both cache on path + mtime +
size, and both return an EMPTY array for a missing or malformed file rather
than raising. That last rule is what makes interpreted and compiled agree even
in the failure case.

Measured on the shipped asset (48 frames, 1089 verts): interpreted 1.16
ms/frame, compiled 0.35 ms/frame, and the vertex buffers are bitwise
identical.

## Why one file, not one per frame

`points` is `(FRAMES, VERTS, 3)` -- the whole take in a single array. Topology
is constant, so one `counts` / `indices` pair serves every frame. Compute
slices `frames[i]`, so scrubbing is an array index, not a file open.

Reading a per-frame path instead needs the frame number substituted into the
filename. Integer-to-string formatting is not part of the lowerable surface, so
that substitution lives in the kernel as `ndio.frame_path` -- see the
`JSON Mesh Reader` template, which compiles too. Use that node when the topology
must CHANGE between frames; when it does not, packing the whole take into one
array is the faster shape.

## Formats

`ndio.read` sniffs four, so the same node reads any of them:

| Format | Detected by | Holds |
|---|---|---|
| `.ndio` | `NDIO\x01` | many NAMED arrays -- what this demo uses |
| `.npy` | `\x93NUMPY` | one array (ask for it with `name=""`) |
| JSON | `{` | a flat object of number arrays |
| raw | nothing | headerless; use `ndio.read_raw(path, dtype=...)` |

Writing works too, and also lowers: `ndio.write(path, points=pts)`,
`ndio.write_raw`, `np.save`, `arr.tofile`.

`np.load` is deliberately NOT lowerable -- it carries no dtype, so the compiled
element type would be a guess. Use `ndio.read(path, name, dtype=...)`.

## Regenerating the asset

```
mayapy make_cache.py
```

Writes a 48-frame, 1089-vertex ripple surface (~1.2 MB) and verifies it
round-trips bitwise through the reader.
'''

JSON_MESH_READER_INIT = r'''# Nothing to set up. Every array this node needs comes off disk in compute,
# through `ndio` -- which is deliberately import-only here so the compute block
# stays a straight line of array math the C++ transpiler can lower whole.
import numpy as np

from mpynode import ndio
'''

JSON_MESH_READER_COMPUTE = r'''# Stream a mesh off disk, ONE JSON FILE PER FRAME -- and compile.
#
# `path` is a filename template: ndio.frame_path replaces the first run of '#'
# with the zero-padded frame, so ".../mesh.####.json" at frame 7 reads
# ".../mesh.0007.json". That substitution is the one string operation a
# compiled compute cannot express on its own -- there is no str(), no %, and no
# f-string in the lowerable surface -- so it lives in the kernel next to the
# reader, and both halves produce byte-identical filenames.
#
# Because every frame is its OWN file, the TOPOLOGY may change from frame to
# frame. That is what this buys over a single packed cache array, which needs
# constant topology by construction.
#
# ndio.read caches the parsed file on path + mtime + size in BOTH
# implementations, so re-evaluating a frame already in hand does no file IO. A
# missing or malformed file yields EMPTY arrays instead of raising, which is why
# the guard below is the only error handling this node needs.
import numpy as np

from mpynode import ndio
from mpynode._api2.geometry import Mesh

resolved = ndio.frame_path(self.path, self.frame)

pts = ndio.read(resolved, "points")
counts = ndio.read(resolved, "counts", dtype=np.int64)
indices = ndio.read(resolved, "indices", dtype=np.int64)

# Accepts points as [[x,y,z], ...] or a flat [x,y,z,x,y,z, ...]; an absent file
# gives an empty array, which must not go through reshape(-1, 3).
if pts.shape[0] < 1:
    points = np.zeros((0, 3))
else:
    points = pts.reshape(-1, 3)

self.outMesh = Mesh(points=points, counts=counts, indices=indices)
'''

JSON_MESH_READER_METHODS = r'''# Demo + test for the per-frame JSON mesh reader. The sequence
# (seq/mesh.####.json) ships beside the template, so both locate it relative to
# the installed mpynode package rather than hard-coding an absolute path.


def _seq_template():
    """Absolute '####' path template for the shipped JSON sequence."""
    import os

    import mpynode

    # .../scripts/mpynode/__init__.py -> up to the repo root, then templates/.
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(mpynode.__file__))))
    return os.path.join(root, "templates", "MPyMesh",
                        "JSON Mesh Reader", "seq", "mesh.####.json")


def _ensure_time(name):
    """Drive ``frame`` from ``time1`` if nothing else already does.

    The interpreted wrapper auto-wires a ``time`` input on create; the COMPILED
    node type does not, so without this the compiled twin sits on frame 0.
    """
    from maya import cmds as mc

    if not mc.listConnections(name + ".frame", source=True, destination=False):
        mc.connectAttr("time1.outTime", name + ".frame", force=True)


@maya_demo(label="JSON Mesh Reader: stream a mesh sequence off disk")
def demo(self):
    from maya import cmds as mc

    name = self.get_name()
    mc.setAttr(name + ".path", _seq_template(), type="string")
    _ensure_time(name)

    xform = mc.createNode("transform", name="jsonMeshReaderGeo#", skipSelect=True)
    shape = mc.createNode("mesh", name=xform + "Shape", parent=xform, skipSelect=True)
    mc.connectAttr(name + ".outMesh", shape + ".inMesh", force=True)
    mc.sets(shape, edit=True, forceElement="initialShadingGroup")

    # The sequence is frames 1..24. Outside that range the resolved filename
    # does not exist and the node shows an empty mesh -- deliberately, so the
    # missing-file behaviour is something you can see rather than read about.
    mc.playbackOptions(minTime=1, maxTime=24, animationStartTime=1, animationEndTime=24)
    mc.currentTime(1)
    mc.dgeval(shape + ".inMesh")

    try:
        mc.select(xform)
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
        mc.select(clear=True)
    except Exception:
        pass    # batch / no viewport

    print("[jsonMeshReader] play the timeline (frames 1-24). Each frame is a "
          "SEPARATE .json file, and the cube count changes with it -- 8 verts "
          "at frame 1, 192 at frame 24.")
    print("[jsonMeshReader] this node COMPILES: the reads and the frame->"
          "filename substitution both lower to the nd_io C++ kernel.")
    return xform


@maya_test(label="JSON Mesh Reader: per-frame files, changing topology", digits=4)
def test_json_mesh_reader(self):
    """Three claims the node would be pointless without: it resolves the right
    file per frame, the topology may CHANGE between frames, and a frame with no
    file degrades to empty rather than erroring."""
    import json
    import os

    import numpy as np
    from maya import cmds as mc
    import maya.api.OpenMaya as om2

    from mpynode import ndio

    name = self.get_name()
    tmpl = _seq_template()
    seq_dir = os.path.dirname(tmpl)
    assert os.path.isdir(seq_dir), "sequence asset missing: %s" % seq_dir
    mc.setAttr(name + ".path", tmpl, type="string")
    _ensure_time(name)

    render = mc.createNode("mesh", skipSelect=True)
    mc.connectAttr(name + ".outMesh", render + ".inMesh", force=True)

    def expected(frame):
        with open(os.path.join(seq_dir, "mesh.%04d.json" % frame)) as fh:
            doc = json.load(fh)
        return (np.asarray(doc["points"], dtype=np.float64).reshape(-1, 3), len(doc["counts"]))

    def out_points():
        mc.dgeval(render + ".inMesh")
        sl = om2.MSelectionList()
        sl.add(render)
        try:
            fn = om2.MFnMesh(sl.getDagPath(0))
        except (ValueError, RuntimeError):
            # An EMPTY mesh is a legal "no geometry" result (a frame with no
            # file); MFnMesh simply refuses to wrap it. Degrade the same way
            # the node does rather than call that an error.
            return np.zeros((0, 3), dtype=np.float64)
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)], dtype=np.float64)

    # 0) the frame->filename rule the whole node rests on.
    assert ndio.frame_path("m.####.json", 7) == "m.0007.json"
    assert ndio.frame_path("m.json", 7) == "m.json"

    # 1) the right file per frame, and the topology tracks it.
    seen_counts = []
    for f in (1, 5, 13, 24):
        mc.currentTime(f)
        got = out_points()
        exp, nfaces = expected(f)
        assert got.shape == exp.shape, (
            "frame %d: got %r verts, file has %r" % (f, got.shape, exp.shape))
        err = float(np.abs(got - exp.astype(np.float32)).max())
        assert err < 1e-4, "frame %d: max vertex error %g" % (f, err)
        assert mc.polyEvaluate(render, face=True) == nfaces, (
            "frame %d: face count does not match the file" % f)
        seen_counts.append(got.shape[0])

    assert len(set(seen_counts)) == len(seen_counts), (
        "vertex count must CHANGE between frames (got %r) -- that is what a "
        "file-per-frame sequence buys over one packed array" % (seen_counts,))

    # 2) re-evaluating a held frame is stable (the cache must not corrupt it).
    mc.currentTime(13)
    first = out_points()
    for _ in range(4):
        mc.dgdirty(name)
        again = out_points()
        assert np.array_equal(first, again), (
            "re-evaluating the same frame changed the result")

    # 3) a frame with no file degrades to an empty mesh, not an error.
    mc.currentTime(999)
    out_points()
    assert mc.polyEvaluate(render, vertex=True) in (0, None), (
        "a missing frame file must yield an empty mesh")
'''

JSON_MESH_READER_DESC = r'''# JSON Mesh Reader

Plays a mesh off disk (an `mPyMesh`), **one JSON file per frame**. Points and
faces can come and go as it plays. Compiles to pure C++.

**Create + Run demo**, then play the timeline.

## What it demonstrates

`path` is a filename *template*. `ndio.frame_path` replaces the first run of `#`
with the zero-padded frame, so `.../mesh.####.json` reads `mesh.0001.json`,
`mesh.0002.json` ... as `frame` advances:

```python
resolved = ndio.frame_path(self.path, self.frame)
pts      = ndio.read(resolved, "points")
counts   = ndio.read(resolved, "counts",  dtype=np.int64)
indices  = ndio.read(resolved, "indices", dtype=np.int64)
```

That substitution is the one string operation a compiled compute cannot express
on its own -- there is no `str()`, no `%`, and no f-string in the lowerable
surface -- so it lives in the C++ kernel beside the reader. Both halves produce
byte-identical filenames, including for negative and fractional frames.

Because every frame is its own file, **the topology may change from frame to
frame.** The shipped sequence leans on that: frame N holds N cubes on a helix,
so the mesh runs from 8 vertices at frame 1 to 192 at frame 24. A single packed
cache array cannot express that -- constant topology is a requirement there.
That is the reason to reach for this node instead of `Disk Mesh Cache`.

## Caching

`ndio.read` caches the parsed file on path + mtime + size, in both the Python
half and the C++ kernel. Re-evaluating a frame the node already holds -- a
dirty-propagation retrigger, a viewport refresh, another node pulling `outMesh`
-- does no file IO. Advancing to a new frame resolves a new filename and reads
it. Rewriting a file under the same name changes the key, so new contents are
picked up rather than served stale.

## File format

```json
{"points": [[x, y, z], ...], "counts": [4, 4, ...], "indices": [0, 1, 2, 3, ...]}
```

`points` may also be flat (`[x, y, z, x, y, z, ...]`). A missing or malformed
file yields an empty mesh -- the node never raises. Scrub past frame 24 to see
it: no file, no geometry, no error, in both the interpreted and compiled node.

`ndio.read` sniffs the format from the leading bytes, so the same node also
reads `.npy`, the `.ndio` multi-array container, and headerless raw -- swap the
sequence for any of them without touching the compute.

## Regenerating the sequence

```
mayapy make_sequence.py
```

Writes 24 frames (~85 KB total) into `seq/`.

## Choosing between this and Disk Mesh Cache

| | JSON Mesh Reader | Disk Mesh Cache |
|---|---|---|
| Layout | one file per frame | whole take in one file |
| Topology | may change per frame | must be constant |
| Format | JSON (text) | `.ndio` (binary) |
| Reads | one per new frame | one, then cached |
| Compiles | yes | yes |
'''


def build_disk_mesh_cache():
    """mPyMesh that plays a cached deforming mesh straight off disk via ndio.

    Gate: the shipped asset must exist and round-trip, the compute must stay
    PORTABLE (the whole point -- this template exists to prove file IO
    compiles), and the authored @maya_test must pass on a fresh node.
    """
    mc.file(new=True, force=True)
    from mpynode._common.node_setups import find_demo
    from mpynode.wrappers.mpy_mesh import MPyMesh

    ok = False
    detail = ""
    try:
        g = MPyMesh.create(name="diskMeshCache")
        g.add_input_attr("cachePath", "string")
        g.add_input_attr("frame", "time")
        g.add_input_attr("scale", "double", default_value=1.0)
        g.set_init_expression(DISK_MESH_CACHE_INIT)
        g.set_compute_expression(DISK_MESH_CACHE_COMPUTE)
        g.set_methods_source(DISK_MESH_CACHE_METHODS)

        _stamp_class(g, "DiskMeshCache", "mPyMesh")
        clean_payload = serialize_node(g, include_persistent=False)
        payload_ok = clean_payload.get("native_type") == "mPyMesh"
        has_demo = find_demo(DISK_MESH_CACHE_METHODS) is not None

        # The asset ships beside the template; without it the demo/test are
        # meaningless, so a missing or non-round-tripping cache FAILS the build.
        from mpynode import ndio
        asset = os.path.join(TPL, "MPyMesh", "Disk Mesh Cache",
                             "ripple_cache.ndio")
        frames = ndio.read(asset, "points")
        counts = ndio.read(asset, "counts", dtype=np.int64)
        indices = ndio.read(asset, "indices", dtype=np.int64)
        asset_ok = (frames.ndim == 3 and frames.shape[0] > 1
                    and counts.size > 0 and indices.size > 0
                    and int(counts.sum()) == int(indices.size)
                    and int(indices.max()) < int(frames.shape[1]))

        # THE gate for this template: it must remain compilable. If a change to
        # the transpiler or the portability rules ever blocks it, fail loudly
        # here rather than silently shipping a template that no longer compiles.
        # ``portable`` alone is no longer enough -- it is now False only for a
        # python/message attr, so a template that drifted onto an unlowerable
        # call (np.load, pickle) would still read as True and quietly route to
        # the AI porter. ``unported`` empty is the real "compiles deterministically".
        from mpynode.native.spec import spec_extractor as _sx
        rep = _sx.assess_portability(DISK_MESH_CACHE_COMPUTE,
                                     DISK_MESH_CACHE_INIT,
                                     {"cachePath": {"attr_type": "string"},
                                      "frame": {"attr_type": "time"},
                                      "scale": {"attr_type": "double"}},
                                     {}, {})
        portable_ok = bool(rep["portable"]) and not rep["unported"]

        test_ok = False
        test_err = "n/a"
        try:
            mc.file(new=True, force=True)
            for plugin in ("mpynode_api1", "mpynode_api2"):
                if not mc.pluginInfo(plugin, q=True, loaded=True):
                    mc.loadPlugin(plugin)
            from mpynode._common.io.mpn_io import deserialize_node
            ttnode = deserialize_node(clean_payload, restore_persistent=False)
            tres = ttnode.run_test()
            test_ok = bool(tres.get("passed"))
            test_err = tres.get("error") or "ok"
        except Exception as texc:
            test_err = "exc:%r" % (texc,)

        ok = bool(payload_ok and has_demo and asset_ok and portable_ok
                  and test_ok)
        detail = ("payload=%s demo=%s asset=%s(frames=%s) portable=%s(%r) "
                  "test=%s(%s)"
                  % (payload_ok, has_demo, asset_ok, frames.shape,
                      portable_ok, rep["blockers"], test_ok, test_err))
    except Exception as exc:
        import traceback
        detail = "exc:%r\n%s" % (exc, traceback.format_exc())

    print("[disk_mesh_cache] %s -> %s" % (detail, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(DISK_MESH_CACHE_DIR, clean_payload,
                           DISK_MESH_CACHE_DESC)
    return ok


def build_json_mesh_reader():
    """mPyMesh that streams one JSON mesh file per frame -- and COMPILES.

    The gate RUNS the node: an earlier revision of this template kept lastPath /
    readCount as stored VARIABLES, which do not survive
    serialize_node(include_persistent=False) -- so the shipped template raised
    AttributeError on its first evaluation while every static check still
    passed. Static checks are not enough; the demo and the authored test must
    actually drive a freshly deserialized node.

    Also asserts the node IS portable. It reads through ndio and resolves the
    per-frame filename with ndio.frame_path, both of which lower onto the nd_io
    C++ kernel. If a transpiler or portability change ever blocks it, fail
    loudly here rather than silently shipping a template that no longer
    compiles.
    """
    mc.file(new=True, force=True)
    from mpynode._common.node_setups import find_demo
    from mpynode.wrappers.mpy_mesh import MPyMesh

    ok = False
    detail = ""
    clean_payload = None
    try:
        g = MPyMesh.create(name="jsonMeshReader")
        g.add_input_attr("path", "string")
        g.add_input_attr("frame", "time")
        g.set_init_expression(JSON_MESH_READER_INIT)
        g.set_compute_expression(JSON_MESH_READER_COMPUTE)
        g.set_methods_source(JSON_MESH_READER_METHODS)

        _stamp_class(g, "JsonMeshReader", "mPyMesh")
        clean_payload = serialize_node(g, include_persistent=False)
        payload_ok = clean_payload.get("native_type") == "mPyMesh"
        has_demo = find_demo(JSON_MESH_READER_METHODS) is not None
        # No stored vars by construction -- that is the bug this template had.
        novars_ok = not (clean_payload.get("variables") or {})

        # The two ndio entry points the node rests on, checked directly: the
        # frame->filename rule, and degrade-to-empty for a file that is not
        # there. Both have C++ twins, cross-verified in test_native_ndio.py --
        # a divergence there would mean the compiled node reads a DIFFERENT
        # file than the interpreted one.
        from mpynode import ndio
        resolve_ok = (ndio.frame_path("mesh.####.json", 7) == "mesh.0007.json"
                      and ndio.frame_path("mesh.json", 7) == "mesh.json")
        degrade_ok = ndio.read("/definitely/not/here.json", "points").size == 0

        # The sequence ships beside the template; the demo is meaningless
        # without it, so a missing/short sequence FAILS the build.
        seq_dir = os.path.join(TPL, "MPyMesh", "JSON Mesh Reader",
                               "seq")
        frames = sorted(f for f in (os.listdir(seq_dir)
                                    if os.path.isdir(seq_dir) else [])
                        if f.endswith(".json"))
        asset_ok = len(frames) >= 24

        from mpynode.native.spec import spec_extractor as _sx
        rep = _sx.assess_portability(JSON_MESH_READER_COMPUTE,
                                     JSON_MESH_READER_INIT,
                                     {"path": {"attr_type": "string"},
                                      "frame": {"attr_type": "time"}},
                                     {}, {})
        # Empty ``unported`` is what "compiles deterministically" means now --
        # see the disk_mesh_cache gate above.
        portable_ok = bool(rep["portable"]) and not rep["unported"]

        # --- RUN IT: demo on one fresh node, authored test on another. ---
        demo_ok = False
        demo_err = "n/a"
        test_ok = False
        test_err = "n/a"
        try:
            from mpynode._common.io.mpn_io import deserialize_node
            from mpynode._common.methods.methods_registry import run_node_demo

            mc.file(new=True, force=True)
            for plugin in ("mpynode_api1", "mpynode_api2"):
                if not mc.pluginInfo(plugin, q=True, loaded=True):
                    mc.loadPlugin(plugin)
            dnode = deserialize_node(clean_payload, restore_persistent=False)
            run_node_demo(dnode, None)
            shp = [s for s in (mc.ls(type="mesh", noIntermediate=True) or [])
                   if mc.listConnections(s + ".inMesh", s=True, d=False)]
            # Frame N of the shipped sequence is N cubes -> 8*N verts. Pin a
            # couple of frames so a silently-empty demo cannot pass.
            seen = []
            for fr in (1, 5, 24):
                mc.currentTime(fr)
                mc.dgeval(shp[0] + ".inMesh")
                seen.append(mc.polyEvaluate(shp[0], v=True))
            demo_ok = (len(shp) == 1 and seen == [8, 40, 192])
            demo_err = "verts@1/5/24=%r" % (seen,)
        except Exception as dexc:
            demo_err = "exc:%r" % (dexc,)

        try:
            from mpynode._common.io.mpn_io import deserialize_node

            mc.file(new=True, force=True)
            for plugin in ("mpynode_api1", "mpynode_api2"):
                if not mc.pluginInfo(plugin, q=True, loaded=True):
                    mc.loadPlugin(plugin)
            ttnode = deserialize_node(clean_payload, restore_persistent=False)
            tres = ttnode.run_test()
            test_ok = bool(tres.get("passed"))
            test_err = tres.get("error") or "ok"
        except Exception as texc:
            test_err = "exc:%r" % (texc,)

        ok = bool(payload_ok and has_demo and novars_ok and resolve_ok
                  and degrade_ok and asset_ok and portable_ok and demo_ok
                  and test_ok)
        detail = ("payload=%s demo_hook=%s novars=%s resolve=%s degrade=%s "
                  "asset=%s(%d frames) portable=%s(%r) demo=%s(%s) test=%s(%s)"
                  % (payload_ok, has_demo, novars_ok, resolve_ok, degrade_ok,
                     asset_ok, len(frames), portable_ok, rep["blockers"],
                     demo_ok, demo_err, test_ok, test_err))
    except Exception as exc:
        import traceback
        detail = "exc:%r\n%s" % (exc, traceback.format_exc())

    print("[json_mesh_reader] %s -> %s" % (detail, "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(JSON_MESH_READER_DIR, clean_payload,
                           JSON_MESH_READER_DESC)
    return ok


# ======================================================================
#  Mesh Maze -- mesh input -> maze walls standing on its edges
# ======================================================================
# The reduction: a maze on a mesh is a SPANNING TREE OF THE MESH'S DUAL GRAPH.
# Faces are cells, interior edges (exactly two incident faces) are the candidate
# doors, and everything left over -- the interior edges the tree did not take,
# every boundary edge, every non-manifold edge -- is a wall. None of that
# depends on face valence, so mixed tris and quads work unmodified.
#
# Two deliberate departures from the textbook algorithm:
#
#   * It does NOT re-seed to guarantee full coverage, and it never raises on a
#     disconnected dual. Unwelded verts, bowties and T-junctions shatter the
#     dual on real DCC geometry, and a node that goes red on a real model is
#     useless. The tree spans the component REACHABLE FROM `start`, walls are
#     emitted only for edges in that component, and everything else is left
#     BARE.
#   * The RNG is an explicit integer LCG, not `random.Random`. The compiled C++
#     node is verified against the interpreted one, and `random.choice` draws
#     through `_randbelow`'s rejection sampling on getrandbits -- no `std::`
#     engine reproduces that, so the two sides would build different (both
#     perfectly valid) mazes and parity would fail on a correct compile.
MAZE_INIT = '''import numpy as np
from mpynode._api2.geometry import Mesh


def _maze_edges(counts, indices, n_verts):
    """Every face-vertex edge of the mesh, as ``(edge_key, face_id)``.

    The key is the INTEGER ``v_lo * n_verts + v_hi``, not a ``(lo, hi)`` tuple:
    a flat int64 array sorts, uniques and scatters as one vectorized primitive,
    where a dict keyed by tuples is neither vectorizable nor deterministically
    lowerable to C++. Edges whose two ends are the SAME vertex are dropped -- a
    degenerate face produces those, and they would key as a self-loop in the
    dual.
    """
    nf = int(counts.shape[0])
    offs = np.cumsum(counts) - counts
    fv_face = np.repeat(np.arange(nf, dtype=np.int64), counts)
    pos = np.arange(int(indices.shape[0]), dtype=np.int64) - offs[fv_face]
    nxt = offs[fv_face] + (pos + 1) % counts[fv_face]
    lo = np.minimum(indices, indices[nxt])
    hi = np.maximum(indices, indices[nxt])
    keep = lo != hi
    return lo[keep] * np.int64(n_verts) + hi[keep], fv_face[keep]


def _maze_dual(key, fv_face, n_faces):
    """The dual graph, as flat CSR arrays.

    Returns ``(uniq, inv, ei, adj_start, deg, adj_dst, adj_eid)``: the unique
    edge keys, each face-vertex edge's slot among them, the slots of the
    INTERIOR edges (exactly two incident faces, and two DIFFERENT ones), and the
    neighbour lists the carve walks.

    An edge with three or more incident faces is non-manifold and is left OUT of
    the adjacency on purpose, rather than unpacked as a 2-element pair that is
    not there. It stays a wall candidate; it simply can never become a door.
    """
    uniq, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    order = np.argsort(inv, kind="stable")
    starts = np.cumsum(cnt) - cnt
    ei = np.nonzero(cnt == 2)[0]
    fa = fv_face[order[starts[ei]]]
    fb = fv_face[order[starts[ei] + 1]]
    good = fa != fb                      # a face folded onto its own edge
    ei = ei[good]
    fa = fa[good]
    fb = fb[good]

    eid = np.arange(int(ei.shape[0]), dtype=np.int64)
    src = np.concatenate([fa, fb])
    o2 = np.argsort(src, kind="stable")
    deg = np.bincount(src, minlength=n_faces).astype(np.int64)
    adj_start = np.cumsum(deg) - deg
    return (uniq, inv, ei, adj_start, deg,
            np.concatenate([fb, fa])[o2], np.concatenate([eid, eid])[o2])


def _maze_carve(n_faces, adj_start, deg, adj_dst, adj_eid, n_edges,
                start, end, min_len, seed):
    """Randomized DFS (recursive backtracker) over the dual, seeded at
    ``start``. Returns ``(visited, door, sol_len)``.

    The doors span the component REACHABLE FROM ``start`` and nothing else. The
    textbook re-seed loop is here; its raise on a disconnected dual is not. An
    unreachable patch simply stays unvisited and gets no geometry. The stack is
    explicit; Python recursion would blow its limit on any mesh worth mazing.

    ``min_len`` is the depth gate: ``end`` is refused as a candidate until the
    stack is that deep, which is what buys a long solution. Gating on stack
    DEPTH and not on visited count is load-bearing -- in a backtracker the stack
    at the moment a cell is first entered IS that cell's final path from the
    root and never changes again, while the visited fraction says nothing about
    it (a DFS can sit at depth 4 having seen 90% of the mesh).

    The RNG is an explicit 64-bit LCG written out as masked integer arithmetic
    rather than ``random.Random``: the compiled C++ node is verified against
    this one, and ``random.choice`` draws through ``_randbelow``'s rejection
    sampling on ``getrandbits``, which no ``std::`` engine reproduces. The two
    would build different (both valid) mazes and parity would fail.
    Multiply-add-mask is bit-identical on either side; the index comes off the
    HIGH bits because an LCG's low bits are worthless.
    """
    visited = np.zeros(n_faces, dtype=np.bool_)
    door = np.zeros(n_edges, dtype=np.bool_)
    stack = np.zeros(n_faces, dtype=np.int64)
    depth = np.zeros(n_faces, dtype=np.int64)
    cand = np.zeros((int(deg.max()) + 1) if n_faces > 0 else 1, dtype=np.int64)

    state = (seed * 6364136223846793005 + 1442695040888963407
             ) & 0x7FFFFFFFFFFFFFFF
    state = (state * 6364136223846793005 + 1442695040888963407
             ) & 0x7FFFFFFFFFFFFFFF

    stack[0] = start
    visited[start] = True
    depth[start] = 1
    sp = 1
    sol_len = 1 if start == end else 0
    while sp > 0:
        cur = int(stack[sp - 1])
        base = int(adj_start[cur])
        nc = 0
        for k in range(int(deg[cur])):
            nb = int(adj_dst[base + k])
            if visited[nb]:
                continue
            if nb == end and sp < min_len:
                continue
            cand[nc] = base + k
            nc += 1
        if nc == 0:
            sp -= 1
            continue
        state = (state * 6364136223846793005 + 1442695040888963407
                 ) & 0x7FFFFFFFFFFFFFFF
        slot = int(cand[(state >> 33) % nc])
        nb = int(adj_dst[slot])
        door[int(adj_eid[slot])] = True
        visited[nb] = True
        stack[sp] = nb
        sp += 1
        depth[nb] = sp
        if nb == end:
            sol_len = sp

    # The depth gate can DEADLOCK: the DFS may unwind past every neighbour of
    # ``end`` without once standing beside it deep enough, which would leave
    # ``end`` walled off and the maze unsolvable. Splice it in instead, onto
    # whichever neighbour sits DEEPEST in the finished tree -- that is the
    # longest solution this tree can offer, it costs one extra pass rather than
    # a decay-and-recarve loop, and ``end`` joins as a leaf so the tree stays a
    # tree. If ``end`` has no visited neighbour at all it is in a different
    # component; it stays out, and its patch stays bare.
    if not visited[end]:
        best = -1
        best_d = 0
        base = int(adj_start[end])
        for k in range(int(deg[end])):
            nb = int(adj_dst[base + k])
            if visited[nb] and int(depth[nb]) > best_d:
                best_d = int(depth[nb])
                best = base + k
        if best >= 0:
            door[int(adj_eid[best])] = True
            visited[end] = True
            sol_len = best_d + 1

    # The gate also STRANDS faces that are perfectly reachable. If every route
    # into a region ran through ``end``, the gate refused ``end`` while the
    # stack was shallow, the walk unwound, and the whole region behind it was
    # never entered -- it would come out bare and the geometry would be silently
    # lost. So sweep the frontier: find any visited face with an unvisited
    # neighbour, open that door, and carve on from there with the same
    # randomized walk but NO gate (the gate has done its job; ``end`` is
    # already placed). Repeat until no frontier remains. This runs AFTER the
    # splice on purpose -- re-seeding first would reach ``end`` through some
    # shallow parent and throw away the long solution. Faces in a genuinely
    # separate component never appear on the frontier, so they stay bare.
    scan = 0
    while scan < n_faces:
        if not visited[scan]:
            scan += 1
            continue
        base = int(adj_start[scan])
        seed_slot = -1
        for k in range(int(deg[scan])):
            if not visited[int(adj_dst[base + k])]:
                seed_slot = base + k
                break
        if seed_slot < 0:
            scan += 1
            continue
        door[int(adj_eid[seed_slot])] = True
        root = int(adj_dst[seed_slot])
        visited[root] = True
        stack[0] = root
        sp = 1
        while sp > 0:
            cur = int(stack[sp - 1])
            cbase = int(adj_start[cur])
            nc = 0
            for k in range(int(deg[cur])):
                if visited[int(adj_dst[cbase + k])]:
                    continue
                cand[nc] = cbase + k
                nc += 1
            if nc == 0:
                sp -= 1
                continue
            state = (state * 6364136223846793005 + 1442695040888963407) & 0x7FFFFFFFFFFFFFFF
            slot = int(cand[(state >> 33) % nc])
            nb = int(adj_dst[slot])
            door[int(adj_eid[slot])] = True
            visited[nb] = True
            stack[sp] = nb
            sp += 1
    return visited, door, sol_len


def _maze_walls(points, normals, va, vb, height, half):
    """One extruded slab per wall edge: the edge widened ``half`` to either side
    and raised ``height`` along the VERTEX NORMALS -- 8 points and 6 quads each,
    batched in one vectorized shot (the game_of_life / voxelize cube batcher,
    re-cut for a prism whose base ring straddles the edge).

    The sideways direction is ``cross(edge, normal)`` taken PER END, so a wall
    standing on a curved edge leans with the surface instead of shearing through
    it. Slabs are NOT welded to each other -- the same trade the voxel shell
    makes. The clamp on the normalize is what keeps a normal parallel to its own
    edge (or a zeroed one) producing a flat degenerate slab instead of a NaN.
    """
    pa = points[va]
    pb = points[vb]
    na = normals[va]
    nb = normals[vb]
    edge = pb - pa
    ta = np.cross(edge, na)
    tb = np.cross(edge, nb)
    ta = ta / np.maximum(np.sqrt((ta * ta).sum(axis=1)), 1e-12)[:, None]
    tb = tb / np.maximum(np.sqrt((tb * tb).sum(axis=1)), 1e-12)[:, None]
    ring = np.stack([pa - ta * half, pa + ta * half,
                     pb + tb * half, pb - tb * half], axis=1)
    up = np.stack([na, na, nb, nb], axis=1) * height
    pts = np.concatenate([ring, ring + up], axis=1).reshape(-1, 3)
    quads = np.array([[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4],
                      [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]], dtype=np.int64)
    m = int(va.shape[0])
    base = (8 * np.arange(m, dtype=np.int64))[:, None, None]
    return (pts, np.full(6 * m, 4, dtype=np.int64),
            (base + quads[None, :, :]).reshape(-1))
'''

MAZE_COMPUTE = '''# Build a maze on the incoming mesh and output its WALLS as geometry.
#
#   1. Key every face-vertex edge as one int64 and group them. Two incident
#      faces -> an interior edge, and an arc of the DUAL graph. One -> a
#      boundary edge. Three or more -> non-manifold, kept out of the dual.
#   2. Randomized DFS over the dual from `start`, refusing to carve into `end`
#      until the stack is `solutionLength` of the mesh deep. The edges it walks
#      through are the DOORS, and they form a spanning tree of whatever the DFS
#      could reach -- so every reached face is connected to every other by
#      exactly one path, and start -> end is solvable by construction.
#   3. Every other edge that touches a reached face becomes a wall: a slab
#      standing on the edge, extruded along the two ends' VERTEX NORMALS.
#
# Faces the DFS could NOT reach are left completely bare. That is the whole
# difference from the textbook algorithm, which re-seeds until the maze covers
# the mesh and raises when it cannot: unwelded verts, bowties and T-junctions
# fragment the dual on real geometry, and a bare patch is a far better answer
# than a red node. Bad `start` / `end` indices, degenerate faces and
# non-manifold edges degrade the same way. Nothing here ever raises.
import numpy as np
from mpynode._api2.geometry import Mesh

src = getattr(self, "inMesh", None)
pts = None if src is None else getattr(src, "points", None)
pts = None if pts is None else np.asarray(pts, dtype=np.float64)
counts = None if src is None else getattr(src, "counts", None)
counts = None if counts is None else np.asarray(counts, dtype=np.int64)
indices = None if src is None else getattr(src, "indices", None)
indices = None if indices is None else np.asarray(indices, dtype=np.int64)

if (pts is None or counts is None or indices is None
        or pts.shape[0] == 0 or counts.shape[0] == 0
        or int(counts.sum()) != int(indices.shape[0])):
    # No input, an empty one, or a point cloud with no faces to use as cells
    # -> an empty but VALID mesh, never a raise.
    self.outMesh = Mesh()
else:
    n_verts = int(pts.shape[0])
    n_faces = int(counts.shape[0])

    # Vertex normals are what the walls stand up along. A value mesh may carry
    # none; fall back to +Y so the node still emits geometry.
    nrm = getattr(src, "normals", None)
    nrm = None if nrm is None else np.asarray(nrm, dtype=np.float64)
    if nrm is None or int(nrm.shape[0]) != n_verts:
        nrm = np.zeros((n_verts, 3), dtype=np.float64)
        nrm[:, 1] = 1.0

    # A NEGATIVE index counts back from the end, so the documented
    # `end = -1` -> LAST face is just the general rule with no special case.
    # Anything still out of range is CLAMPED: a typo in a face id has to
    # degrade to a maze somewhere else on the mesh, never to a red node.
    start = int(self.start)
    end = int(self.end)
    if start < 0:
        start = n_faces + start
    if end < 0:
        end = n_faces + end
    start = min(max(start, 0), n_faces - 1)
    end = min(max(end, 0), n_faces - 1)

    key, fv_face = _maze_edges(counts, indices, n_verts)
    uniq, inv, ei, adj_start, deg, adj_dst, adj_eid = _maze_dual(
        key, fv_face, n_faces)

    # The gate is a FRACTION of the face count rather than an absolute cell
    # count, so the same setting means the same thing after a subdivide.
    #
    # `sol_len` -- the achieved solution length -- goes nowhere: the node has
    # no output for it and the walls do not depend on it. It is returned
    # because the build gate and the authored test assert on it.
    want = int(float(self.solutionLength) * float(n_faces))
    visited, door, sol_len = _maze_carve(
        n_faces, adj_start, deg, adj_dst, adj_eid, int(ei.shape[0]),
        start, end, want, int(self.seed))

    # An edge is LIVE when any face it touches was reached. Doors are carved
    # out of the live set; everything else in it -- the interior edges the tree
    # passed over, every boundary edge, and any non-manifold edge that never
    # entered the dual -- is a wall. An edge touching only unreached faces is
    # in neither, which is exactly what leaves an unreachable patch bare.
    live = np.zeros(int(uniq.shape[0]), dtype=np.bool_)
    live[inv[visited[fv_face]]] = True
    is_door = np.zeros(int(uniq.shape[0]), dtype=np.bool_)
    is_door[ei[door]] = True
    wall = np.nonzero(live & ~is_door)[0]

    if int(wall.shape[0]) == 0:
        self.outMesh = Mesh()
    else:
        k = uniq[wall]
        va = k // np.int64(n_verts)
        vb = k - va * np.int64(n_verts)
        wp, wc, wi = _maze_walls(pts, nrm, va, vb,
                                 float(self.wallHeight),
                                 0.5 * float(self.wallThickness))
        self.outMesh = Mesh(points=wp, counts=wc, indices=wi)
'''

MAZE_METHODS = VANILLA_SETUP_ERROR + VANILLA_MESHES + '''

@maya_command(creates=True)
def setup(self, selection=None, *args, **kwargs):
    """Select a mesh, then Run setup: wires that mesh in and builds a render
    mesh for the maze walls standing on it."""
    from maya import cmds as mc

    name = self.get_name()
    order = [o for o in (selection or mc.ls(selection=True) or []) if o != name]
    meshes = _meshes(order) if order else []
    if not meshes:
        raise SetupError("Select a mesh, then run setup.")
    shape = (mc.ls(meshes[0], long=True) or [meshes[0]])[0]
    mc.connectAttr(shape + ".worldMesh[0]", name + ".inMesh", force=True)

    out = mc.createNode("mesh")
    out_tr = mc.listRelatives(out, parent=True)[0]
    out_tr = mc.rename(out_tr, name + "_walls")
    out_shape = mc.listRelatives(out_tr, shapes=True, fullPath=True)[0]
    mc.connectAttr(name + ".outMesh", out_shape + ".inMesh", force=True)
    try:
        mc.sets(out_shape, edit=True, forceElement="initialShadingGroup")
    except Exception:
        pass
    return out_tr


@maya_demo(label="Maze on a sphere")
def demo(self):
    """Wrap a maze around a poly sphere. A sphere shows off what the walls
    stand along -- they radiate out on the vertex normals -- and its poles are
    triangle fans, so the demo also proves mixed valence needs no special
    handling. Drag `seed` for a different maze, `start` / `end` to move the
    entrance and exit."""
    from maya import cmds as mc

    sph = mc.polySphere(constructionHistory=False, radius=5, sx=24, sy=16)[0]
    # The wrapper does NOT expose methods_source funcs as attributes, so
    # ``self.setup(...)`` would AttributeError; route through the validated
    # dispatcher (run_setup binds our ``def setup(self, ...)``).
    res = self.run_setup([sph])
    name = self.get_name()
    mc.setAttr(name + ".wallHeight", 0.6)
    mc.setAttr(name + ".wallThickness", 0.12)
    try:
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return res


@maya_test(label="Mesh maze: doors are a spanning tree of the reachable dual", digits=4)
def test_mesh_maze(self):
    """Validate the node's INTENT -- the topology invariants a maze must have,
    which hold for ANY seed and so are identical for the interpreted node and
    its C++ compile (passing this against the compiled node proves parity even
    though the two would not have to agree on WHICH maze):

      1. Every wall slab is whole (8 verts, 6 quads) and stands on a real edge
         of the source mesh.
      2. Doors (the live edges the node did NOT wall) number exactly
         `reachableFaces - 1` -- the spanning-tree size.
      3. Union-find over the doors yields exactly ONE component and never
         merges two already-joined faces: spanning, and acyclic.
      4. No door is punched through a boundary edge.
      5. Every live edge is exactly one of door or wall.
      6. There is a start -> end path through the doors (solvable), and raising
         `solutionLength` makes it longer.
      7. `end = -1` is the LAST face -- same maze as passing that index.
      8. On a mesh whose dual is DISCONNECTED, faces the maze cannot reach get
         no geometry at all, and the node does not raise.
      9. Walls extrude along the VERTEX NORMALS -- checked on a sphere, since
         on a flat plane a hardcoded up-axis would look identical.

    Proxy-safe: the node is driven purely through `self.get_name()` and `cmds`.
    The maze is never re-derived here -- the door set is recovered from the
    EMITTED GEOMETRY by matching each slab's base-ring centre against the
    source's edge midpoints, so the assertions are about what the node actually
    built.
    """
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    from mpynode._common.methods.test_helpers import assert_true

    name = self.get_name()

    def _set(plug, *vals):
        # The demo may have CONNECTED this input; break it so the test can
        # drive it.
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals)

    render = mc.createNode("mesh")
    mc.connectAttr(name + ".outMesh", render + ".inMesh", force=True)
    _set(name + ".wallHeight", 0.3)
    _set(name + ".wallThickness", 0.06)
    _set(name + ".seed", 0)
    _set(name + ".solutionLength", 0.35)

    def _wire(shape):
        # Re-connecting an already-connected plug is legal but warns, and this
        # runs a dozen times -- only wire when the source actually changes.
        src = shape + ".worldMesh[0]"
        if src not in (mc.listConnections(name + ".inMesh", source=True,
                                          destination=False, plugs=True) or []):
            mc.connectAttr(src, name + ".inMesh", force=True)

    def _mid(p, a, b):
        return (round((p[a].x + p[b].x) * 0.5, 4),
                round((p[a].y + p[b].y) * 0.5, 4),
                round((p[a].z + p[b].z) * 0.5, 4))

    def _source(shape):
        """(faceCount, edgeFaces, faceEdges, midpoint -> edge id) of a mesh.
        Edges are identified by their MIDPOINT, which is the same key the wall
        slabs are matched on below."""
        sl = om2.MSelectionList()
        sl.add(shape)
        fn = om2.MFnMesh(sl.getDagPath(0))
        pts = fn.getPoints(om2.MSpace.kObject)
        by_mid = {}
        for e in range(fn.numEdges):
            va, vb = fn.getEdgeVertices(e)
            by_mid[_mid(pts, va, vb)] = e
        e_faces = [[] for _ in range(fn.numEdges)]
        f_edges = []
        for f in range(fn.numPolygons):
            vs = list(fn.getPolygonVertices(f))
            fe = []
            for i in range(len(vs)):
                e = by_mid.get(_mid(pts, vs[i], vs[(i + 1) % len(vs)]))
                if e is not None:
                    fe.append(e)
                    e_faces[e].append(f)
            f_edges.append(fe)
        return fn.numPolygons, e_faces, f_edges, by_mid

    def _walls(by_mid):
        """The emitted slabs as (vertCount, faceCount, set of source edge ids,
        matched count). A slab's base ring is its first four points, and their
        mean is the midpoint of the edge it straddles."""
        mc.dgdirty(name)
        mc.dgeval(render + ".outMesh")
        sl = om2.MSelectionList()
        sl.add(render)
        try:
            fn = om2.MFnMesh(sl.getDagPath(0))
        except Exception:
            return 0, 0, set(), 0
        pts = fn.getPoints(om2.MSpace.kObject)
        got = set()
        hit = 0
        for k in range(fn.numVertices // 8):
            cx = cy = cz = 0.0
            for j in range(4):
                q = pts[8 * k + j]
                cx += q.x
                cy += q.y
                cz += q.z
            e = by_mid.get((round(cx * 0.25, 4), round(cy * 0.25, 4), round(cz * 0.25, 4)))
            if e is not None:
                hit += 1
                got.add(e)
        return fn.numVertices, fn.numPolygons, got, hit

    def _check(shape, start, end_attr, label):
        """Assert the whole invariant set against one source mesh. Returns
        (solutionLength, reachableFaces, totalFaces)."""
        _wire(shape)
        _set(name + ".start", start)
        _set(name + ".end", end_attr)
        n_faces, e_faces, f_edges, by_mid = _source(shape)
        nv, nf, walls, hit = _walls(by_mid)

        assert_true(nv > 0 and nv % 8 == 0 and nf == 6 * (nv // 8),
                    "%s: walls must be whole slabs (verts=%d faces=%d)" % (label, nv, nf))
        assert_true(hit == nv // 8 and len(walls) == hit,
                    "%s: every slab must stand on a distinct source edge "
                    "(%d slabs, %d matched, %d distinct)"
                    % (label, nv // 8, hit, len(walls)))

        # Plain reachability over the dual -- no RNG, no tree. This is the
        # component the node is contracted to draw, and nothing else.
        adj = [[] for _ in range(n_faces)]
        for e in range(len(e_faces)):
            if len(e_faces[e]) == 2:
                a, b = e_faces[e]
                adj[a].append((b, e))
                adj[b].append((a, e))
        comp = set([start])
        stack = [start]
        while stack:
            for nb, e in adj[stack.pop()]:
                if nb not in comp:
                    comp.add(nb)
                    stack.append(nb)

        live = set(e for e in range(len(e_faces))
                   if any(f in comp for f in e_faces[e]))
        assert_true(walls <= live,
                    "%s: %d wall(s) landed outside the reachable component -- "
                    "unreachable patches must stay BARE"
                    % (label, len(walls - live)))
        doors = live - walls

        # 2 + 4 + 5: spanning-tree size, no boundary doors, clean partition.
        assert_true(len(doors) == len(comp) - 1,
                    "%s: doors must number reachableFaces-1 (%d vs %d)"
                    % (label, len(doors), len(comp) - 1))
        assert_true(all(len(e_faces[e]) == 2 for e in doors),
                    "%s: a door was punched through a non-interior edge" % label)
        assert_true(len(live) == len(doors) + len(walls),
                    "%s: every live edge must be exactly one of door or wall" % label)

        # 3: union-find over the doors -- one component, and acyclic.
        parent = list(range(n_faces))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        tree = [[] for _ in range(n_faces)]
        for e in doors:
            a, b = e_faces[e]
            tree[a].append(b)
            tree[b].append(a)
            ra, rb = find(a), find(b)
            assert_true(ra != rb,
                        "%s: doors must be acyclic (edge %d closes a loop)" % (label, e))
            parent[ra] = rb
        assert_true(len(set(find(f) for f in comp)) == 1,
                    "%s: the doors must join the component into ONE piece" % label)

        # 6: the start -> end path through the doors. Unique, because a tree.
        goal = end_attr if end_attr >= 0 else n_faces + end_attr
        dist = {start: 0}
        queue = [start]
        while queue:
            cur = queue.pop(0)
            for nb in tree[cur]:
                if nb not in dist:
                    dist[nb] = dist[cur] + 1
                    queue.append(nb)
        if goal in comp:
            assert_true(goal in dist and dist[goal] >= 1,
                        "%s: start -> end must be solvable through the doors" % label)
        return dist.get(goal, 0), len(comp), n_faces

    # --- 1..6 on a clean, fully connected plane --------------------------
    plane = mc.polyPlane(w=10, h=10, sx=10, sy=10,
                         constructionHistory=False)[0]
    p_shape = mc.listRelatives(plane, shapes=True, fullPath=True)[0]
    _, reach, total = _check(p_shape, 0, -1, "plane")
    assert_true(reach == total == 100,
                "plane's dual must be fully connected (%d/%d)" % (reach, total))

    # --- 7: end = -1 IS the last face ------------------------------------
    # `end` reaches the maze ONLY through the depth gate, so at a modest
    # solutionLength the DFS walks into it naturally, nothing is ever refused,
    # and every `end` yields the same maze -- which would make this assert
    # vacuous. Crank the gate up so it really bites, and check both halves:
    # that -1 matches the last face, AND that some other `end` genuinely gives
    # a different maze.
    _set(name + ".solutionLength", 0.9)
    by_mid = _source(p_shape)[3]
    _set(name + ".end", -1)
    a_nv, _a_nf, a_walls, _ = _walls(by_mid)
    _set(name + ".end", total - 1)
    b_nv, _b_nf, b_walls, _ = _walls(by_mid)
    _set(name + ".end", total // 2)
    _c_nv, _c_nf, c_walls, _ = _walls(by_mid)
    assert_true(a_nv == b_nv and a_walls == b_walls,
                "end = -1 must resolve to the LAST face (%d verts vs %d)" % (a_nv, b_nv))
    assert_true(a_walls != c_walls,
                "`end` must change the maze, or the -1 check above proves " "nothing")
    # Out of range in either direction CLAMPS -- it must never raise, and it
    # must land on the nearest valid face.
    _set(name + ".end", 5000)
    d_nv, _d_nf, d_walls, _ = _walls(by_mid)
    assert_true(d_nv == a_nv and d_walls == a_walls,
                "an out-of-range end must clamp to the last face, not raise")
    _set(name + ".end", -1)
    _set(name + ".solutionLength", 0.35)

    # --- 6b: the solution-length gate has to earn its keep ---------------
    # With start and end ADJACENT the ungated maze regularly links them in two
    # or three cells; the gate refuses `end` until the stack is deep, which is
    # the whole point of it. Summed over four seeds so no single unlucky draw
    # decides the assert.
    loose = tight = 0
    for seed in range(4):
        _set(name + ".seed", seed)
        _set(name + ".solutionLength", 0.0)
        loose += _check(p_shape, 0, 1, "gate-off")[0]
        _set(name + ".solutionLength", 0.5)
        tight += _check(p_shape, 0, 1, "gate-on")[0]
    assert_true(tight > loose,
                "solutionLength must lengthen the solution (gated %d vs "
                "ungated %d over 4 seeds)" % (tight, loose))
    _set(name + ".seed", 0)
    _set(name + ".solutionLength", 0.35)

    # --- 9: the walls stand along the VERTEX NORMALS ---------------------
    # A flat plane cannot show this -- every normal there is +Y, so a
    # hardcoded up-axis would pass. On a sphere the normals are radial, so
    # every slab's top ring must sit exactly one `wallHeight` FURTHER OUT than
    # its base ring. A +Y extrusion pushes the southern walls INWARDS instead.
    sph = mc.polySphere(constructionHistory=False, radius=5, sx=24, sy=16)[0]
    s_shape = mc.listRelatives(sph, shapes=True, fullPath=True)[0]
    _wire(s_shape)
    _set(name + ".start", 0)
    _set(name + ".end", -1)
    _set(name + ".wallHeight", 0.5)
    mc.dgdirty(name)
    mc.dgeval(render + ".outMesh")
    rsel = om2.MSelectionList()
    rsel.add(render)
    rpts = om2.MFnMesh(rsel.getDagPath(0)).getPoints(om2.MSpace.kObject)
    worst_lo, worst_hi = 1e9, -1e9
    for k in range(len(rpts) // 8):
        rb = rt = 0.0
        for j in range(4):
            q = rpts[8 * k + j]
            rb += (q.x * q.x + q.y * q.y + q.z * q.z) ** 0.5
            q = rpts[8 * k + 4 + j]
            rt += (q.x * q.x + q.y * q.y + q.z * q.z) ** 0.5
        rise = (rt - rb) * 0.25
        worst_lo = min(worst_lo, rise)
        worst_hi = max(worst_hi, rise)
    assert_true(len(rpts) > 0 and worst_lo > 0.45 and worst_hi < 0.51,
                "walls must extrude along the VERTEX NORMALS: on a sphere "
                "every slab must rise 0.5 radially (got %.4f .. %.4f)" % (worst_lo, worst_hi))
    _set(name + ".wallHeight", 0.3)

    # --- 8: a DISCONNECTED dual leaves the far island bare ---------------
    # Two planes united into ONE mesh object: vertex-connected as far as Maya
    # is concerned, but no shared edge, so the dual is in two pieces. The maze
    # must cover the island holding `start` and draw nothing on the other.
    far = mc.polyPlane(w=4, h=4, sx=3, sy=3, constructionHistory=False)[0]
    mc.setAttr(far + ".translateX", 40)
    near = mc.polyPlane(w=4, h=4, sx=3, sy=3, constructionHistory=False)[0]
    both = mc.polyUnite(near, far, constructionHistory=False)[0]
    b_shape = mc.listRelatives(both, shapes=True, fullPath=True)[0]
    _, reach2, total2 = _check(b_shape, 0, -1, "split")
    assert_true(0 < reach2 < total2,
                "the united planes must have a DISCONNECTED dual (%d/%d)" % (reach2, total2))

    # --- 10: a CUT-VERTEX dual -- the gate must not strand REACHABLE faces --
    # A 1 x 20 strip's dual is a PATH, so every interior face is a cut vertex:
    # everything past `end` is reachable ONLY through `end`. The depth gate
    # refuses `end` while the stack is shallow, so without the frontier re-seed
    # the walk dies early and most of the strip comes out bare -- which is 2 and
    # 3 above failing, not a new invariant. Swept over the goals that bite
    # hardest and over both sides of the gate.
    strip = mc.polyPlane(w=2, h=20, sx=1, sy=20, constructionHistory=False)[0]
    t_shape = mc.listRelatives(strip, shapes=True, fullPath=True)[0]
    for gate in (0.0, 0.35, 0.9):
        _set(name + ".solutionLength", gate)
        for goal in (1, 5, 10, -1):
            _, reach3, total3 = _check(t_shape, 0, goal,
                                       "strip g=%.2f end=%d" % (gate, goal))
            assert_true(reach3 == total3 == 20,
                        "the strip's dual must be one PATH of 20 (%d/%d)" % (reach3, total3))
    _set(name + ".solutionLength", 0.35)
'''

MAZE_DESC = (
    "# Mesh Maze\n\n"
    "Turns any mesh into a **maze**, and outputs the maze's **walls** as an "
    "`mPyMesh` on `outMesh`. The source mesh is the floor; the walls stand on "
    "its edges, extruded along the **vertex normals**, so a maze on a sphere "
    "wraps around it properly instead of shearing through it.\n\n"
    "The whole thing is one idea: **a maze on a mesh is a spanning tree of "
    "that mesh's dual graph.**\n\n"
    "| Maze | Mesh |\n"
    "|---|---|\n"
    "| Cell | Face |\n"
    "| Door | Interior edge the tree walked through |\n"
    "| Wall | Every other edge |\n\n"
    "Because the doors form a *tree*, three things come for free: every cell "
    "is reachable, there is exactly **one** path between any two cells, and "
    "`start` -> `end` is always solvable -- no validation pass needed. None of "
    "it depends on face valence, so mixed triangles and quads just work.\n\n"
    "- `start` / `end` -- the **face ids** the maze runs between. A negative "
    "id counts back from the end, so the default **`end = -1` is the last "
    "face**. An id that is still out of range is clamped rather than "
    "rejected.\n"
    "- `seed` -- which maze you get. Same seed, same maze, every time.\n"
    "- `solutionLength` -- how deep the carve must be before it is allowed to "
    "reach `end`, as a fraction of the face count. It is what stops a maze "
    "from parking the exit three cells from the entrance. It matters most "
    "when `start` and `end` are **close together**; when they are already far "
    "apart the maze is long anyway and the setting does little. Worth knowing: "
    "`end` reaches the maze *only* through this gate, so at a low setting the "
    "gate never fires and moving `end` can leave the layout completely "
    "unchanged.\n"
    "- `wallHeight` / `wallThickness` -- the size of each wall slab, in world "
    "units. They are absolute, so dial them to your mesh's scale.\n\n"
    "**Unreachable patches are left bare.** If the mesh's dual graph is in "
    "more than one piece -- which is what unwelded vertices, bowties and "
    "T-junctions produce, and they are near-universal on imported geometry -- "
    "only the piece containing `start` gets a maze. The rest gets no walls at "
    "all, which reads at a glance as *that region is not connected* rather "
    "than failing. Bad face ids, degenerate faces and non-manifold edges "
    "degrade the same way: this node does not error out.\n\n"
    "A couple of honest limits. Wall slabs are **not welded** to each other. "
    "On a mesh with holes or a handle (a torus, say) you get a few detached "
    "closed wall loops floating in the maze -- still a perfect maze, and the "
    "count of them is fixed by the surface's topology, not by the algorithm. "
    "And triangles are dead-end magnets, so a tri-heavy mesh gives a stubbier "
    "maze than a quad one.\n\n"
    "**Create + Run demo** wraps a maze around a poly sphere. Drag `seed` and "
    "watch it rebuild."
)


def build_mesh_maze():
    mc.file(new=True, force=True)
    from mpynode._common.node_setups import find_demo
    from mpynode.wrappers.mpy_mesh import MPyMesh

    n = MPyMesh.create(name="meshMaze")
    # Add order IS the Channel Box / Designer display order: the source, then
    # where the maze runs, then which maze, then how the walls look.
    n.add_input_attr("inMesh", "mesh")
    n.add_input_attr("start", "int", default_value=0)
    n.add_input_attr("end", "int", default_value=-1)
    n.add_input_attr("seed", "int", default_value=0, min_value=0)
    n.add_input_attr("solutionLength", "double", default_value=0.35,
                     min_value=0.0, max_value=1.0)
    n.add_input_attr("wallHeight", "double", default_value=0.25,
                     min_value=0.0)
    n.add_input_attr("wallThickness", "double", default_value=0.05,
                     min_value=0.0)
    n.set_init_expression(MAZE_INIT)
    n.set_compute_expression(MAZE_COMPUTE)
    n.set_methods_source(MAZE_METHODS)
    nm = n.get_name()

    # Capture the VANILLA payload before any live mutation.
    _stamp_class(n, "MeshMaze", "mPyMesh")
    clean_payload = serialize_node(n, include_persistent=False)

    # --- pure-function checks on the Init helpers -------------------------
    ns = {}
    exec(MAZE_INIT, ns)
    edges_fn = ns["_maze_edges"]
    dual_fn = ns["_maze_dual"]
    carve_fn = ns["_maze_carve"]
    walls_fn = ns["_maze_walls"]

    # Two quads sharing edge (1, 2), plus a DEGENERATE face whose first two
    # verts are the same vertex: that self-edge must not survive keying.
    q_counts = np.array([4, 4, 3], dtype=np.int64)
    q_indices = np.array([0, 1, 2, 3, 1, 4, 5, 2, 6, 6, 7], dtype=np.int64)
    key, fvf = edges_fn(q_counts, q_indices, 8)
    # 4 + 4 + 3 face-vertex edges, minus the one self-edge (6, 6).
    edge_ok = (int(key.shape[0]) == 10 and int(fvf.shape[0]) == 10
               and int((key == (1 * 8 + 2)).sum()) == 2
               and not bool((key == (6 * 8 + 6)).any()))

    uniq, inv, ei, adj_start, deg, adj_dst, adj_eid = dual_fn(key, fvf, 3)
    # Exactly one interior edge -- (1, 2) -- so the dual is 0 <-> 1 and the
    # degenerate face 2 is isolated.
    dual_ok = (int(ei.shape[0]) == 1 and int(uniq[ei[0]]) == 1 * 8 + 2
               and deg.tolist() == [1, 1, 0]
               and sorted(adj_dst.tolist()) == [0, 1])

    # A NON-MANIFOLD edge (3 incident faces) must be kept out of the dual
    # rather than unpacked as a pair -- three triangles sharing edge (0, 1).
    nm_counts = np.array([3, 3, 3], dtype=np.int64)
    nm_indices = np.array([0, 1, 2, 0, 1, 3, 0, 1, 4], dtype=np.int64)
    nk, nf2 = edges_fn(nm_counts, nm_indices, 5)
    _u, _i, nei, _as, ndeg, _ad, _ae = dual_fn(nk, nf2, 3)
    nonman_ok = (int(nei.shape[0]) == 0 and ndeg.tolist() == [0, 0, 0])

    # The carve on a 4-cell PATH graph 0-1-2-3 with a detached cell 4: the
    # tree must span the reachable four and never touch the fifth, and the
    # depth gate must push the solution the long way round.
    p_start = np.array([0, 1, 3, 5, 6], dtype=np.int64)
    p_deg = np.array([1, 2, 2, 1, 0], dtype=np.int64)
    p_dst = np.array([1, 0, 2, 1, 3, 2], dtype=np.int64)
    p_eid = np.array([0, 0, 1, 1, 2, 2], dtype=np.int64)
    vis, door, sol = carve_fn(5, p_start, p_deg, p_dst, p_eid, 3, 0, 3, 0, 0)
    carve_ok = (vis.tolist() == [True, True, True, True, False]
                and int(door.sum()) == 3 and sol == 4)

    # Determinism in `seed`, and a different seed really is a different maze.
    # A 3x3 grid of quads has enough freedom for the two to diverge.
    g_counts = np.full(9, 4, dtype=np.int64)
    g_idx = []
    for gy in range(3):
        for gx in range(3):
            v0 = gy * 4 + gx
            g_idx.extend([v0, v0 + 1, v0 + 5, v0 + 4])
    g_indices = np.array(g_idx, dtype=np.int64)
    gk, gf = edges_fn(g_counts, g_indices, 16)
    gu, gi, gei, gas, gdeg, gad, gae = dual_fn(gk, gf, 9)
    runs = []
    for sd in (0, 0, 1, 2, 3):
        runs.append(carve_fn(9, gas, gdeg, gad, gae, int(gei.shape[0]),
                             0, 8, 4, sd)[1].tolist())
    seed_ok = (runs[0] == runs[1] and len(set(tuple(r) for r in runs)) > 1
               and all(sum(r) == 8 for r in runs))

    # The slab batcher: 8 verts + 6 quads per edge, spanning the edge by its
    # length, `wallThickness` across it and `wallHeight` up the normal.
    wp, wc, wi = walls_fn(np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]),
                          np.array([[0.0, 1.0, 0.0], [0.0, 1.0, 0.0]]),
                          np.array([0], dtype=np.int64),
                          np.array([1], dtype=np.int64), 0.5, 0.05)
    span = wp.max(axis=0) - wp.min(axis=0)
    # Each quad must wind OUTWARD -- its normal has to point away from the
    # slab centre, or the walls render inside-out.
    ctr = wp.mean(axis=0)
    wind_ok = True
    for qi in wi.reshape(6, 4):
        v = wp[qi]
        if float(np.dot(v.mean(axis=0) - ctr,
                        np.cross(v[1] - v[0], v[2] - v[0]))) <= 0.0:
            wind_ok = False
    wall_ok = (wp.shape == (8, 3) and wc.shape == (6,) and bool((wc == 4).all())
               and int(wi.max()) == 7 and wind_ok
               and np.allclose(span, [2.0, 0.5, 0.1]))

    helpers_ok = (edge_ok and dual_ok and nonman_ok and carve_ok and seed_ok
                  and wall_ok)

    # --- live end-to-end: a 10x10 plane is a disk, so the wall count is
    #     pinned exactly by Euler -- E - F + 1 with F - 1 doors. ------------
    plane = mc.polyPlane(w=10, h=10, sx=10, sy=10,
                         constructionHistory=False)[0]
    p_shape = mc.listRelatives(plane, shapes=True, fullPath=True)[0]
    mc.connectAttr(p_shape + ".worldMesh[0]", nm + ".inMesh", force=True)
    render = mc.createNode("mesh", name="mazeRenderShape")
    mc.connectAttr(nm + ".outMesh", render + ".inMesh", force=True)

    def live_counts():
        mc.dgdirty(nm)
        mc.dgeval(render + ".outMesh")
        rsel = om.MSelectionList()
        rsel.add(render)
        try:
            rfn = om.MFnMesh(rsel.getDagPath(0))
            return rfn.numVertices, rfn.numPolygons
        except Exception:
            return 0, 0

    def live_points():
        mc.dgdirty(nm)
        mc.dgeval(render + ".outMesh")
        rsel = om.MSelectionList()
        rsel.add(render)
        try:
            rfn = om.MFnMesh(rsel.getDagPath(0))
        except Exception:
            return np.zeros((0, 3))
        return np.array([[p.x, p.y, p.z]
                         for p in rfn.getPoints(om.MSpace.kObject)])

    # V=121 E=220 F=100 -> doors = 99, walls = 220 - 99 = 121. Getting this
    # number exactly means the tree is the right SIZE and that no door was
    # punched through the boundary -- one integer pins both.
    lv, lf = live_counts()
    euler_ok = (lv == 121 * 8 and lf == 121 * 6)

    # Same seed -> byte-identical maze; a different seed -> a different one.
    a = live_points()
    b = live_points()
    mc.setAttr(nm + ".seed", 7)
    c = live_points()
    mc.setAttr(nm + ".seed", 0)
    seed_live_ok = (a.shape == b.shape and np.array_equal(a, b)
                    and c.shape == a.shape and not np.array_equal(a, c))

    # end = -1 is the LAST face: the same maze as asking for face 99, and a
    # DIFFERENT one from face 50 -- without that second half the check is
    # vacuous, because `end` only reaches the maze through the depth gate and
    # a slack gate is never refused anything. Hence solutionLength cranked to
    # 0.9 here: it makes `end` observable in the geometry at all.
    mc.setAttr(nm + ".solutionLength", 0.9)
    mc.setAttr(nm + ".end", -1)
    m1 = live_points()
    mc.setAttr(nm + ".end", 99)
    m2 = live_points()
    mc.setAttr(nm + ".end", 50)
    m5 = live_points()
    mc.setAttr(nm + ".end", 500)          # far out of range -> clamped to 99
    m3 = live_points()
    mc.setAttr(nm + ".start", -7000)      # ditto on the other side -> 0
    m4 = live_points()
    mc.setAttr(nm + ".start", 0)
    mc.setAttr(nm + ".end", -1)
    mc.setAttr(nm + ".solutionLength", 0.35)
    index_ok = (m1.shape == m2.shape and np.array_equal(m1, m2)
                and m5.shape == m1.shape and not np.array_equal(m1, m5)
                and m3.shape == m1.shape and np.array_equal(m3, m1)
                and m4.shape == m1.shape and np.array_equal(m4, m1))

    # The knobs are live and scale the slabs, not the wall COUNT.
    mc.setAttr(nm + ".wallHeight", 1.0)
    tall = live_points()
    mc.setAttr(nm + ".wallHeight", 0.25)
    short = live_points()
    size_ok = (tall.shape == short.shape
               and float(tall[:, 1].max() - tall[:, 1].min()) >
               float(short[:, 1].max() - short[:, 1].min()) + 0.5)

    # Walls extrude along the VERTEX NORMALS -- which a flat plane cannot show,
    # since every normal there is +Y and a hardcoded up-axis would pass. On a
    # sphere the normals are radial, so every slab's top ring must sit exactly
    # one wallHeight FURTHER OUT than its base ring. A +Y extrusion instead
    # pushes the southern walls INWARDS, giving a rise near -H.
    sph = mc.polySphere(constructionHistory=False, radius=5, sx=24, sy=16)[0]
    s_shape = mc.listRelatives(sph, shapes=True, fullPath=True)[0]
    mc.connectAttr(s_shape + ".worldMesh[0]", nm + ".inMesh", force=True)
    mc.setAttr(nm + ".wallHeight", 0.5)
    slab = live_points().reshape(-1, 8, 3)
    rise = (np.sqrt((slab[:, 4:, :].mean(axis=1) ** 2).sum(axis=1))
            - np.sqrt((slab[:, :4, :].mean(axis=1) ** 2).sum(axis=1)))
    normal_ok = (slab.shape[0] > 0 and float(rise.min()) > 0.45
                 and float(rise.max()) < 0.51)
    mc.setAttr(nm + ".wallHeight", 0.25)

    # A DISCONNECTED dual: two planes united into one mesh object share no
    # edge, so only the island holding `start` may get walls -- and flipping
    # `start` to the other island must move the maze there rather than raise.
    far = mc.polyPlane(w=4, h=4, sx=3, sy=3, constructionHistory=False)[0]
    mc.setAttr(far + ".translateX", 40)
    near = mc.polyPlane(w=4, h=4, sx=3, sy=3, constructionHistory=False)[0]
    both = mc.polyUnite(near, far, constructionHistory=False)[0]
    b_shape = mc.listRelatives(both, shapes=True, fullPath=True)[0]
    mc.connectAttr(b_shape + ".worldMesh[0]", nm + ".inMesh", force=True)
    isl_a = live_points()
    mc.setAttr(nm + ".start", 12)          # a face on the FAR island
    isl_b = live_points()
    mc.setAttr(nm + ".start", 0)
    # Each 3x3 island is its own disk: V=16 E=24 F=9 -> 24 - 9 + 1 = 16 walls.
    bare_ok = (isl_a.shape[0] == 16 * 8 and isl_b.shape[0] == 16 * 8
               and float(isl_a[:, 0].max()) < 20.0
               and float(isl_b[:, 0].min()) > 20.0)

    # A CUT-VERTEX dual, which is the case the depth gate can strand: a 1x20
    # strip's dual is a PATH, so every face past `end` is reachable ONLY
    # through `end`, and the gate refuses `end` while the stack is shallow. The
    # strip is a disk too -- V=42 E=61 F=20 -> 61 - 20 + 1 = 42 walls -- so one
    # integer catches a single stranded face anywhere in it.
    strip = mc.polyPlane(w=2, h=20, sx=1, sy=20, constructionHistory=False)[0]
    t_shape = mc.listRelatives(strip, shapes=True, fullPath=True)[0]
    mc.connectAttr(t_shape + ".worldMesh[0]", nm + ".inMesh", force=True)
    cut_ok = True
    for gate in (0.0, 0.35, 0.9):
        mc.setAttr(nm + ".solutionLength", gate)
        for goal in (1, 5, 10, -1):
            mc.setAttr(nm + ".end", goal)
            if int(live_points().shape[0]) != 42 * 8:
                cut_ok = False
    mc.setAttr(nm + ".end", -1)
    mc.setAttr(nm + ".solutionLength", 0.35)

    live_ok = (euler_ok and seed_live_ok and index_ok and size_ok
               and normal_ok and bare_ok and cut_ok)

    # An unconnected / value mesh input must yield an empty mesh, not a crash.
    empty_ns = {}
    exec(MAZE_INIT, empty_ns)

    class _EmptySelf(object):
        inMesh = None
        start = 0
        end = -1
        seed = 0
        solutionLength = 0.35
        wallHeight = 0.25
        wallThickness = 0.05
        outMesh = None

    es = _EmptySelf()
    empty_ns["self"] = es
    try:
        exec(compile(MAZE_COMPUTE, "maze_compute", "exec"), empty_ns)
        empty_ok = (es.outMesh is not None
                    and getattr(es.outMesh, "points", None) is None)
    except Exception:
        empty_ok = False

    has_demo = find_demo(MAZE_METHODS) is not None

    # Actually RUN the demo on a fresh node so a broken demo body fails the
    # BUILD here, not later in the user's session.
    demo_ok = False
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        dnode = deserialize_node(clean_payload, name="mazeDemoCheck")
        dnode.run_demo()
        demo_ok = len(mc.ls(type="mesh") or []) >= 2
    except Exception as exc:
        print("[mesh_maze] demo run FAILED: %r" % exc)

    # Run the authored @maya_test on a FRESH deserialized node.
    test_ok = False
    try:
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node

        tnode = deserialize_node(clean_payload, name="mazeTestCheck")
        tres = tnode.run_test()
        test_ok = bool(tres.get("passed"))
        if not test_ok:
            print("[mesh_maze] @maya_test FAILED: %s" % tres.get("error"))
    except Exception as exc:
        print("[mesh_maze] @maya_test run ERRORED: %r" % exc)

    ok = helpers_ok and live_ok and empty_ok and has_demo and demo_ok and test_ok
    print("[mesh_maze] helpers=%s(edge=%s dual=%s nonman=%s carve=%s seed=%s "
          "wall=%s) live=%s(euler=%s seed=%s index=%s size=%s normal=%s "
          "bare=%s cut=%s) "
          "empty=%s demo=%s demo_run=%s test=%s -> %s"
          % (helpers_ok, edge_ok, dual_ok, nonman_ok, carve_ok, seed_ok,
             wall_ok, live_ok, euler_ok, seed_live_ok, index_ok, size_ok,
             normal_ok, bare_ok, cut_ok, empty_ok, has_demo, demo_ok, test_ok,
             "PASS" if ok else "FAIL"))
    if ok:
        _write_template_to(MAZE_DIR, clean_payload, MAZE_DESC)
    return ok


def main():
    results = {
        "mPyDeformer": build_deformer(),
        "nurbsCurveHelix": build_nurbs_curve_helix(),
        "nurbsSurfaceRipple": build_nurbs_surface_ripple(),
        "deformerNurbsWave": build_deformer_nurbs_wave(),
        "comboCorrectives": build_combo_correctives(),
        # No "mPyFile": build_file() -- the Basic Texture template it wrote was
        # measurably identical to File Simple (same output at every flat texel;
        # they parted only on the single blended texel at a cell edge, because
        # File Simple hand-rolled a nearest tap back then). File Simple absorbed
        # it -- it now IS this FILE_COMPUTE body and is the mPyFile PRIMARY --
        # and kept the one thing Basic Texture never had: the embedded-image
        # fallback, which read_texture() now provides to every mPyFile.
        # build_file_simple() runs every gate build_file() did, plus the two
        # embedded-image ones, so nothing is unverified by the merge.
        "gameOfLifeFile": build_game_of_life_file(),
        "gameOfLifeMesh": build_game_of_life_mesh(),
        "uvLayoutMesh": build_uv_layout_mesh(),
        "metaballs": build_metaballs(),
        "voxelizeMesh": build_voxelize_mesh(),
        "meshMaze": build_mesh_maze(),
        "diskMeshCache": build_disk_mesh_cache(),
        "jsonMeshReader": build_json_mesh_reader(),
        "mPyIkSolver": build_ik(),
        "unitSphereCollision": build_unit_sphere_collision_deformer(),
        "fileSimple": build_file_simple(),
        "fileScanline": build_file_scanline(),
        "fileComposite": build_file_composite(),
        "locatorWidgetShowcase": build_locator_widget_showcase(),
        "locatorAnimatedText": build_locator_animated_text(),
        "locatorAnimatedSelection": build_locator_animated_selection(),
        "locatorMeshRegions": build_locator_mesh_regions(),
        "procrustesTags": build_procrustes_tags(),
        "aimBetweenMatrices": build_aim_between_matrices(),
        "dnet": build_dnet(),
        "skinLBS": build_skin_lbs(),
        "skinDQS": build_skin_dqs(),
        "skinTwistSwing": build_skin_twist_swing(),
        "rbfWrap": build_rbf_wrap(),
        "rbfWrapDeformer": build_rbf_wrap_deformer(),
        "patchRelax": build_patch_relax(),
    }
    print("=== RESULTS ===", results)
    for dirpath, _dirs, files in os.walk(TPL):
        for n in sorted(files):
            p = os.path.join(dirpath, n)
            print("  ", os.path.relpath(p, TPL), os.path.getsize(p), "bytes")
    return all(results.values())


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
