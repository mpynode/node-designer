"""Functional + structural checks for the DNET spring-network solver template
(``MPyNode/DNET``).

DNET is a base ``mPyNode`` that runs a damped Jacobi spring relaxation each
frame: knots carry goal transforms (``matrices[]``), links (``index0``/
``index1``) are springs with rest lengths, and ``positions[]`` outputs each
knot's solved offset in its goal's parent space. The whole template is built
from just two authoring commands -- ``create_knot`` and ``create_link`` -- and
all three demos assemble their scenes through them:

* **Grid Net** -- a pinned 6x8 grid built with ``draw_icon=False`` (lightweight:
  goal + RESULT child + a tiny marker, NO icosahedron proxy). The four corners
  are anchored; animating the top-right corner makes the interior swing.
* **Layout Net (JSON)** -- a 30-knot / 38-link mouth membrane built with
  ``draw_icon=True`` (icosahedron proxy per knot, a line per link), then rigged
  to ``skull.ma``'s jaw + cranium (a midway transform for the mouth corners, the
  upper lip on the cranium, the lower lip on the jaw).
* **Two Knots (Shapes)** -- the minimal net (2 free hubs + 4 anchors + 5 links),
  the same shape scheme end to end.

These tests drive the node through the REAL gallery path (_TemplateCreateCommand:
create -> apply template -> run demo), then scrub / drag to prove the net solves
(corners stay pinned, interior swings) rather than merely that connections
landed. A Compute error ships an all-zero output WITHOUT raising -- which would
vacuously satisfy the "at rest ~0" checks -- so the behavioral sweeps subscribe
to the log bus and the load-bearing assertion is that a knot MOVED.
"""

import os
import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init
from mpynode._base.commands import _TemplateCreateCommand, run_undoable
from mpynode._common.io.mpn_io import load_mpn
from mpynode._node_registry import wrap_node


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_TPL = os.path.join(os.environ["MPYNODE_ROOT"], "templates")
_REL = "MPyNode/DNET"

# The grid demo's fixed net (must match DEMO_DNET in build_templates.py).
_ROWS, _COLS = 6, 8
_N = _ROWS * _COLS
_CORNERS = [0, _COLS - 1, (_ROWS - 1) * _COLS, _N - 1]
_INTERIOR = [r * _COLS + c for r in range(1, _ROWS - 1)
             for c in range(1, _COLS - 1)]
_GRID_LINKS = _ROWS * (_COLS - 1) + (_ROWS - 1) * _COLS   # 42 + 40 = 82


def _payload(rel):
    path = os.path.join(_TPL, *rel.split("/"), "template.mpn")
    data = load_mpn(path, trusted=True)
    return data, data.get("native_type")


def _create_with_demo(rel):
    payload, native_type = _payload(rel)
    mc.select(clear=True)
    cmd = _TemplateCreateCommand(payload, native_type, run_demo=True)
    name = run_undoable(cmd) or cmd.created_name
    if cmd.tier_failures.get("demo"):
        raise AssertionError("demo failed: %s" % cmd.tier_failures["demo"])
    return name


def _create_vanilla(rel):
    """Create the template node WITHOUT running its demo -- a bare dnet ready to
    be authored by hand via its create_knot / create_link Methods commands."""
    payload, native_type = _payload(rel)
    mc.select(clear=True)
    cmd = _TemplateCreateCommand(payload, native_type, run_demo=False)
    return run_undoable(cmd) or cmd.created_name


def _mag(v):
    return (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5


def _decode_stored_vars(sv):
    """Decode a template's stored_vars field to its mapping (``{}`` when empty).

    ``load_mpn`` may hand back the raw keyed2/zlib envelope (a dict or its JSON
    string), so normalise it here rather than assuming a decoded value."""
    import base64
    import json
    import zlib

    if not sv:
        return {}
    if isinstance(sv, dict) and "data_b64" in sv:
        raw = base64.b64decode(sv["data_b64"])
        if sv.get("codec") == "zlib":
            raw = zlib.decompress(raw)
        return json.loads(raw.decode("utf-8") or "{}")
    if isinstance(sv, str):
        try:
            inner = json.loads(sv)
        except ValueError:
            return {}
        return _decode_stored_vars(inner)
    if isinstance(sv, dict):
        return sv
    return {}


class _ErrSink(object):
    """Collect any expression-error broadcast on the log bus."""

    def __init__(self):
        self.errors = []

    def append_message(self, message, level):
        if level == "error" or "expression error" in message:
            self.errors.append(message)


def _link_nodes(name):
    """The dnet's link transforms -- the sources feeding ``tension[]`` (each link
    is a transform carrying its own tension/push/pull wired to a per-link slot)."""
    return sorted(set(mc.listConnections(name + ".tension", source=True,
                                         destination=False) or []))


class DnetTemplateStructureTest(unittest.TestCase):
    def test_template_files_and_type(self):
        base = os.path.join(_TPL, *_REL.split("/"))
        self.assertTrue(os.path.isfile(os.path.join(base, "template.mpn")),
                        "dnet template.mpn missing")
        self.assertTrue(os.path.isfile(os.path.join(base, "description.md")),
                        "dnet description.md missing")
        self.assertTrue(os.path.isfile(os.path.join(base, "skull.ma")),
                        "dnet skull.ma asset missing (needed by demo_layout)")
        data, native_type = _payload(_REL)
        self.assertEqual(native_type, "mPyNode",
                         "dnet must be a base mPyNode, got %r" % native_type)
        inputs = data.get("input_attrs") or {}
        outputs = data.get("output_attrs") or {}
        for a in ("matrices", "anchors", "index0", "index1", "restLengths",
                  "tension", "push", "pull", "iterations", "damping",
                  "tolerance", "resetBuffer", "evaluate", "inverseMatrix",
                  "time"):
            self.assertIn(a, inputs, "dnet missing input %r" % a)
        # solved parent-space positions, per-link lengths, iterations, max force.
        for o in ("positions", "lengths", "maxIterations", "maxForce"):
            self.assertIn(o, outputs, "dnet missing output %r" % o)
        # vanilla template bakes NO solver state: stored_vars must decode to {}.
        self.assertEqual(_decode_stored_vars(data.get("stored_vars")), {},
                         "dnet template unexpectedly bakes stored vars")

    def test_payload_carries_node_identity(self):
        # Creating from this template stamps the canonical Class
        # mpynode_user.MPyDnet and names it via payload["preferred_name"].
        data, _ = _payload(_REL)
        self.assertEqual(data.get("class_path"), "mpynode_user.MPyDnet",
                         "dnet template must stamp class_path mpynode_user.MPyDnet")
        self.assertEqual(data.get("preferred_name"), "mPyDnet1",
                         "dnet template must prefer the node name mPyDnet1")

    def test_created_node_named_mpydnet_and_tagged(self):
        # Prove the payload identity survives the REAL gallery create path.
        mc.file(new=True, force=True)
        name = _create_vanilla(_REL)
        self.assertEqual(name.split("|")[-1], "mPyDnet1",
                         "template create must name the node mPyDnet1, got %r"
                         % name)
        self.assertEqual(wrap_node(name).get_py_class(), "mpynode_user.MPyDnet",
                         "created dnet node not stamped mpynode_user.MPyDnet")

    def test_template_imports_shared_solver_and_vendors_commands(self):
        # The two halves pull in OPPOSITE directions, and this guards both.
        # Solver: extracted to mpynode._common.nodes.rigging.dnet, so the Init
        # tab must IMPORT it rather than bake the blob back in.
        # create_knot / create_link: must NOT. A @maya_command ships as embedded
        # python inside the .mll, and on a machine with Maya but WITHOUT mpynode
        # the delegating `import ... as _impl` raised ModuleNotFoundError -- so
        # their bodies are VENDORED into the methods source.
        data, _ = _payload(_REL)
        init_src = data.get("init_source") or ""
        methods = data.get("methods_source") or ""
        self.assertIn("from mpynode._common.nodes.rigging.dnet import Solver",
                      init_src,
                      "Init tab must import the shared Solver, not define it")
        # the heavy kernel source must NOT be baked in any more.
        self.assertNotIn("_evaluate_parallel", init_src,
                         "Init tab still bakes the Solver kernel source")
        self.assertNotIn("def _buildAdjacency", init_src,
                         "Init tab still bakes the adjacency kernel source")
        for fn in ("create_knot", "create_link"):
            self.assertNotIn(
                "from mpynode._common.nodes.rigging.dnet import %s as _impl" % fn,
                methods,
                "%s must carry its own body: a @maya_command cannot import "
                "mpynode, it ships inside the .mll" % fn)
        # ...and the vendored bodies are THERE (a dropped body would otherwise
        # pass the assertNotIn above).
        for marker in ('name="dnetGoal#"', 'name="dnetLink#"'):
            self.assertIn(marker, methods,
                          "the vendored create_knot/create_link body is missing "
                          "from the methods source (%s not found)" % marker)

    def test_three_demos_render_a_submenu(self):
        # THREE demos -> the "Run demo" UI renders a SUBMENU (1 -> flat action).
        # find_demos is the static, exec-free source the UI counts. Order is by
        # lineno, so the grid net stays PRIMARY -- what run_demo() with no name
        # and the gallery's run_demo=True target.
        from mpynode._common.node_setups import find_demos, demo_labels

        data, _ = _payload(_REL)
        source = data.get("methods_source") or ""
        self.assertTrue(source, "dnet template carries no methods source")

        specs = find_demos(source)
        self.assertEqual(len(specs), 3,
                         "dnet must ship three demos for the Run-demo submenu, "
                         "got %d" % len(specs))
        self.assertEqual(demo_labels(source),
                         ["Grid Net", "Layout Net (JSON)", "Two Knots (Shapes)"],
                         "demo labels/order wrong (grid must stay primary)")
        self.assertEqual(specs[0].func_name, "demo",
                         "the grid net must be the first (primary) demo")
        self.assertEqual(specs[1].func_name, "demo_layout",
                         "the JSON layout net must be the second demo")
        self.assertEqual(specs[2].func_name, "demo_two_knots",
                         "the two-knot pure-shapes demo must be the third demo")


class DnetGridDemoTest(unittest.TestCase):
    """The PRIMARY demo (``@maya_demo`` "Grid Net"): a pinned 6x8 grid built with
    create_knot(draw_icon=False) + create_link(draw_icon=False). Each knot is a
    GOAL (worldMatrix -> matrices[i], anchored -> anchors[i]) with a RESULT child
    riding positions[i] and a tiny marker sphere; each edge a lightweight link
    transform (tension/push/pull -> per-link slots, NO curve). No icosahedron
    proxies, no blendShapes, no gizmos -- the cheap variant that keeps 48 knots
    responsive."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _positions(self, name, frame):
        mc.currentTime(frame)
        mc.dgdirty(name + ".positions")
        return [mc.getAttr(name + ".positions[%d]" % i)[0] for i in range(_N)]

    def test_demo_builds_pinned_grid_net_and_swings(self):
        from mpynode._common.util import log_bus

        name = _create_with_demo(_REL)

        # 48 goal transforms feed matrices[]; 48 RESULT children ride positions[].
        goals = set(mc.listConnections(name + ".matrices", source=True,
                                       destination=False) or [])
        children = set(mc.listConnections(name + ".positions", source=False,
                                          destination=True) or [])
        self.assertEqual(len(goals), _N, "expected %d goal transforms" % _N)
        self.assertEqual(len(children), _N, "expected %d knot children" % _N)
        self.assertEqual(mc.getAttr(name + ".positions", size=True), _N,
                         "positions output not sized to the knot count")
        self.assertEqual(mc.getAttr(name + ".index0", size=True), _GRID_LINKS,
                         "index0 not sized to the %d grid springs" % _GRID_LINKS)

        # each RESULT child is a CHILD of its goal (world = goal + positions),
        # its translate driven by positions[i]; a marker sphere rides it.
        for c in children:
            parent = (mc.listRelatives(c, parent=True, fullPath=True) or [None])[0]
            self.assertIsNotNone(parent, "%s has no parent goal" % c)
            src = mc.listConnections(c + ".translate", source=True,
                                     destination=False) or []
            self.assertTrue(src, "%s.translate not driven" % c)
        self.assertEqual(len(mc.ls("dnetKnotMarker*", type="transform") or []),
                         _N, "expected one marker sphere per knot")

        # LIGHTWEIGHT: draw_icon=False -> no icosahedron blendShapes, no gizmos.
        self.assertFalse(mc.ls(type="blendShape") or [],
                         "grid demo must be lightweight (no knot blendShapes)")
        self.assertFalse(mc.ls(type="mPyLocator") or [],
                         "grid demo must build no mPyLocator gizmos")
        self.assertFalse(mc.ls(type="mPyTransform") or [],
                         "grid demo must build no aim mPyTransforms")

        # anchors: 1 at the four corners, 0 in the interior.
        for i in _CORNERS:
            self.assertEqual(mc.getAttr(name + ".anchors[%d]" % i), 1.0,
                             "corner %d not anchored" % i)
        for i in _INTERIOR:
            self.assertEqual(mc.getAttr(name + ".anchors[%d]" % i), 0.0,
                             "interior knot %d unexpectedly anchored" % i)

        # A Compute crash ships an all-zero output silently, passing the
        # rest/corner checks vacuously -- hence the log bus, and "an interior
        # knot MOVED" as the load-bearing check.
        sink = _ErrSink()
        log_bus.subscribe(sink)
        try:
            d1 = self._positions(name, 1)     # rest grid: spacing == rest length
            d24 = self._positions(name, 24)   # top-right corner pulled out of plane
        finally:
            log_bus.unsubscribe(sink)
        self.assertFalse(sink.errors,
                         "dnet compute broadcast an expression error while "
                         "scrubbing: %s" % sink.errors)

        # Frame 1: the grid is at rest -> every knot's goal-local displacement ~0.
        self.assertLess(max(_mag(v) for v in d1), 1e-2,
                        "net not at rest on frame 1")
        # Corners are anchored -> local displacement ~0 even when the goal moves.
        self.assertLess(max(_mag(d1[i]) for i in _CORNERS), 1e-3,
                        "a corner drifted at rest")
        self.assertLess(max(_mag(d24[i]) for i in _CORNERS), 1e-3,
                        "a corner drifted when the net swung")
        # Frame 24: at least one interior knot clearly moved (the net swings).
        self.assertGreater(max(_mag(d24[i]) for i in _INTERIOR), 0.05,
                           "no interior knot moved when the corner was animated")

    def test_tension_contracts_net_toward_anchors(self):
        # Red-green for the PER-LINK `tension` array. tension[e] shortens link e's
        # effective rest length, so raising it pulls the free interior knots
        # inward toward the anchored corners. tension[e] is CONNECTED, so drive it
        # through the LINK transforms as a user would. Two properties, because
        # "the net moved" is not enough:
        #   1. magnitude grows with tension -> guards a DROPPED per-link read.
        #   2. motion is CONTRACTION, not expansion -> guards a SIGN-FLIPPED term.
        name = _create_with_demo(_REL)
        mc.setAttr(name + ".resetBuffer", 1)     # clean re-seed every eval
        mc.setAttr(name + ".iterations", 200)    # let contraction develop
        mc.currentTime(1)
        links = _link_nodes(name)
        self.assertEqual(len(links), _GRID_LINKS,
                         "expected %d link transforms" % _GRID_LINKS)

        # Grid center in the goals' grid frame (goal i at (i%cols, -i//cols), unit
        # spacing). Solved world pos = goalPos + positions[i], and distance-to-
        # center is translation-invariant, so the goal group's offset cancels.
        cx, cy = (_COLS - 1) / 2.0, -(_ROWS - 1) / 2.0

        def measure(tension):
            for link in links:                       # tension is per-link now
                mc.setAttr(link + ".tension", tension)
            mc.dgdirty(name + ".positions")
            max_mag = 0.0
            dist_to_center = 0.0
            for i in _INTERIOR:
                v = mc.getAttr(name + ".positions[%d]" % i)[0]
                max_mag = max(max_mag, _mag(v))
                wx = float(i % _COLS) + v[0]        # solved world pos (grid frame)
                wy = -float(i // _COLS) + v[1]
                dist_to_center += ((wx - cx) ** 2 + (wy - cy) ** 2
                                   + v[2] ** 2) ** 0.5
            return max_mag, dist_to_center

        slack_mag, slack_dist = measure(0.0)   # no tension -> interior at rest
        taut_mag, taut_dist = measure(1.0)     # full tension -> interior inward

        self.assertLess(slack_mag, 1e-2,
                        "interior should sit at the rest grid with tension=0")
        self.assertGreater(taut_mag, slack_mag + 0.05,
                           "raising tension did not move the net "
                           "(per-link tension dropped?): slack=%.4f taut=%.4f"
                           % (slack_mag, taut_mag))
        self.assertLess(taut_dist, slack_dist - 0.05,
                        "raising tension did not contract the net toward its "
                        "anchors (tension term sign-flipped?): slack_dist=%.4f "
                        "taut_dist=%.4f" % (slack_dist, taut_dist))

    def test_asymmetric_link_topology_does_not_silently_collapse(self):
        # index0/index1 are INDEPENDENT dense arrays, so a hand-edited topology
        # can leave index0 longer. The adjacency kernel indexes both in lock-step,
        # so an unpaired tail used to raise IndexError inside compute -- swallowed,
        # shipping an all-zero positions[] SILENTLY. Compute now truncates both to
        # the shared link count. (index0[] is setAttr, not connected, so appending
        # a bare entry is legal here.)
        from mpynode._common.util import log_bus

        name = _create_with_demo(_REL)
        # append one extra index0 entry with NO matching index1 -> len mismatch.
        extra = mc.getAttr(name + ".index0", size=True)
        mc.setAttr(name + ".index0[%d]" % extra, 5)
        mc.setAttr(name + ".resetBuffer", 1)     # deterministic single-eval solve
        mc.setAttr(name + ".iterations", 200)
        mc.currentTime(24)                        # corner pulled out -> net swings

        sink = _ErrSink()
        log_bus.subscribe(sink)
        try:
            mc.dgdirty(name + ".positions")
            d = [mc.getAttr(name + ".positions[%d]" % i)[0] for i in range(_N)]
        finally:
            log_bus.unsubscribe(sink)

        self.assertFalse(sink.errors,
                         "unpaired index0/index1 crashed compute: %s"
                         % sink.errors)
        # and it did NOT collapse to all-zero: the extra link is dropped, the
        # corners stay pinned, and the interior still swings.
        self.assertLess(max(_mag(d[i]) for i in _CORNERS), 1e-3,
                        "a corner drifted after dropping the unpaired link")
        self.assertGreater(max(_mag(d[i]) for i in _INTERIOR), 0.05,
                           "net collapsed to all-zero (unpaired link crashed "
                           "compute instead of dropping the extra endpoint)")


class DnetLayoutDemoTest(unittest.TestCase):
    """The SECOND demo (``@maya_demo`` "Layout Net (JSON)"): the 30-knot / 38-link
    mouth membrane, built with the SHAPE scheme (create_knot / create_link,
    draw_icon=True) and rigged to a skull.

    Each knot is a GOAL (worldMatrix -> matrices[i], with an ``anchored`` weight
    -> anchors[i] and a ``radius``) plus a RESULT child riding positions[i]; a
    hidden PROXY icosahedron shape on the child worldspace-blendShapes onto the
    visible icosahedron shape on the goal, so the visible icon lands on the solved
    knot. Each link is a plain transform (``tension``/``push``/``pull`` -> the
    per-link solver slots, ``inheritsTransform`` OFF) parenting a degree-1 line
    whose 2 CVs track the two knots' RESULT children (a decomposeMatrix per CV).

    Part B: skull.ma's jaw + cranium drive the net. A ``midway`` transform is
    point-constrained to the jaw and orient-constrained to BOTH jaw and cranium
    (equal weights -> it rotates halfway) and the mouth-CORNER goals ride it; the
    upper-lip goals follow the cranium, the lower-lip goals follow the jaw. Run BY
    NAME through the wrapper's run_demo on a bare (no-demo) node."""

    _LN = 30                                   # knots in the captured layout
    _LE = 38                                   # links
    # Free (unanchored) knots per the layout anchors[] (0 == free).
    _FREE = [1, 3, 5, 7, 9, 11, 13, 15]

    def setUp(self):
        mc.file(new=True, force=True)
        self.name = _create_vanilla(_REL)      # bare dnet: no demo run yet

    def _goal_of(self, i):
        return (mc.listConnections(self.name + ".matrices[%d]" % i, source=True,
                                   destination=False) or [None])[0]

    def _child_of(self, i):
        """The RESULT child riding positions[i] (its translate destination)."""
        for p in (mc.listConnections(self.name + ".positions[%d]" % i,
                                     source=False, destination=True,
                                     plugs=True) or []):
            if p.rsplit(".", 1)[1] == "translate":
                return p.rsplit(".", 1)[0]
        return None

    def test_layout_builds_shape_net_and_skull_rig(self):
        from mpynode._common.util import log_bus

        # Run the SECOND demo by name. A crash mid-demo ships silently, so guard
        # the run with the log bus.
        sink = _ErrSink()
        log_bus.subscribe(sink)
        try:
            wrap_node(self.name).run_demo("demo_layout")
        finally:
            log_bus.unsubscribe(sink)
        self.assertFalse(sink.errors,
                         "layout demo broadcast an error: %s" % sink.errors)

        n = self.name
        # 30 knots feed matrices[]; 38 links feed index0[]/index1[].
        self.assertEqual(mc.getAttr(n + ".positions", size=True), self._LN,
                         "positions not sized to the 30 captured knots")
        self.assertEqual(mc.getAttr(n + ".index0", size=True), self._LE,
                         "index0 not sized to the 38 captured links")
        self.assertEqual(mc.getAttr(n + ".index1", size=True), self._LE,
                         "index1 not sized to the 38 captured links")

        # 30 distinct GOAL meshes drive matrices[]; each is a polygon icosahedron.
        goal_nodes = set(mc.listConnections(n + ".matrices", source=True,
                                            destination=False) or [])
        self.assertEqual(len(goal_nodes), self._LN,
                         "expected %d knot goals on matrices[]" % self._LN)
        for g in goal_nodes:
            self.assertTrue(mc.listRelatives(g, shapes=True, type="mesh") or [],
                            "goal %s is not a polygon mesh (icosahedron)" % g)

        # 30 worldspace blendShapes (proxy -> goal) at full weight; the OLD
        # gizmo/aim scheme is gone.
        blends = mc.ls(type="blendShape") or []
        self.assertEqual(len(blends), self._LN,
                         "expected %d knot blendShapes, got %d"
                         % (self._LN, len(blends)))
        for bs in blends:
            self.assertAlmostEqual(mc.getAttr(bs + ".weight[0]"), 1.0, places=6,
                                   msg="blendShape %s not at full weight" % bs)
        self.assertFalse(mc.ls(type="mPyLocator") or [],
                         "layout demo must build no mPyLocator gizmos")
        self.assertFalse(mc.ls(type="mPyTransform") or [],
                         "layout demo must build no aim mPyTransforms")

        # 38 link transforms: own tension/push/pull wired to the matching
        # per-link slot, inheritsTransform OFF, exactly one line.
        for attr in ("tension", "push", "pull"):
            plugs = (mc.listConnections(n + "." + attr, source=True,
                                        destination=False, plugs=True) or [])
            self.assertEqual(len(plugs), self._LE,
                             "expected %d %s[e] slots wired, got %d"
                             % (self._LE, attr, len(plugs)))
            self.assertTrue(all(p.split(".", 1)[1] == attr for p in plugs),
                            "%s must be fed by the link's own %s attr, got %s"
                            % (attr, attr, plugs))
        links = _link_nodes(n)
        self.assertEqual(len(links), self._LE,
                         "expected %d link transforms" % self._LE)
        for link in links:
            self.assertEqual(mc.getAttr(link + ".inheritsTransform"), 0,
                             "link %s must have inheritsTransform OFF" % link)
            crv = mc.listRelatives(link, shapes=True, type="nurbsCurve",
                                   fullPath=True) or []
            self.assertEqual(len(crv), 1,
                             "link %s must parent exactly ONE line curve" % link)

        # Anchor partition: 8 free, 22 pinned -- matching the captured layout.
        free = [i for i in range(self._LN)
                if abs(mc.getAttr(n + ".anchors[%d]" % i)) < 0.5]
        self.assertEqual(sorted(free), self._FREE,
                         "free-knot set does not match the captured layout")

        # ---- Part B: skull rig ----
        self.assertTrue(mc.objExists("jaw") and mc.objExists("cranium"),
                        "skull.ma jaw/cranium not imported by demo_layout")
        self.assertEqual(len(mc.ls(type="parentConstraint") or []), self._LN,
                         "expected one parentConstraint per knot goal")
        self.assertEqual(len(mc.ls(type="pointConstraint") or []), 1,
                         "expected the midway transform's single pointConstraint")
        self.assertEqual(len(mc.ls(type="orientConstraint") or []), 1,
                         "expected the midway transform's single orientConstraint")
        self.assertTrue(mc.ls("dnetJawMidway*", type="transform") or [],
                        "no dnetJawMidway transform built")

        # Geometry-derived driver assignment: corners (4,5,12,13) -> the midway
        # transform; upper-lip (e.g. 0) -> cranium; lower-lip (e.g. 6) -> jaw.
        def drivers_of(i):
            g = self._goal_of(i)
            try:
                return set(mc.parentConstraint(g, query=True,
                                               targetList=True) or [])
            except Exception:
                return set()

        self.assertTrue(any("dnetJawMidway" in d for d in drivers_of(4)),
                        "mouth-corner knot 4 not driven by the midway transform")
        self.assertIn("cranium", drivers_of(0),
                      "upper-lip knot 0 not driven by the cranium")
        self.assertIn("jaw", drivers_of(6),
                      "lower-lip knot 6 not driven by the jaw")

    def test_layout_solver_responds_to_tension_and_icon_tracks(self):
        # Raising tension pulls the free knots off rest while the anchored knots
        # stay pinned -- and the visible icosahedron must track its solved RESULT
        # child (the worldspace blendShape actually deforming).
        from mpynode._common.util import log_bus

        wrap_node(self.name).run_demo("demo_layout")
        n = self.name
        links = _link_nodes(n)
        self.assertEqual(len(links), self._LE,
                         "expected %d link transforms" % self._LE)
        free = [i for i in range(self._LN)
                if abs(mc.getAttr(n + ".anchors[%d]" % i)) < 0.5]
        pinned = [i for i in range(self._LN) if i not in free]

        mc.setAttr(n + ".resetBuffer", 1)
        mc.setAttr(n + ".iterations", 200)

        def free_disp():
            mc.dgdirty(n + ".positions")
            return max(_mag(mc.getAttr(n + ".positions[%d]" % i)[0]) for i in free)

        sink = _ErrSink()
        log_bus.subscribe(sink)
        try:
            slack = free_disp()                        # tension 0 -> at rest
            for link in links:
                mc.setAttr(link + ".tension", 1.0)     # contract every link
            taut = free_disp()                         # tension 1 -> contracted
            pinned_disp = max(_mag(mc.getAttr(n + ".positions[%d]" % i)[0])
                              for i in pinned)
        finally:
            log_bus.unsubscribe(sink)

        self.assertFalse(sink.errors,
                         "layout net errored under tension: %s" % sink.errors)
        self.assertLess(slack, 1e-2,
                        "free knots should sit at rest with tension 0")
        self.assertGreater(taut, slack + 0.05,
                           "raising tension did not move the free knots "
                           "(handle not reaching the solver?): slack=%.4f "
                           "taut=%.4f" % (slack, taut))
        self.assertLess(pinned_disp, 1e-2,
                        "an anchored knot drifted under tension")

        # The visible icosahedron on a free knot's goal must land on the solved
        # RESULT child (the blendShape deforms the goal onto the child).
        fi = free[0]
        goal, child = self._goal_of(fi), self._child_of(fi)
        self.assertIsNotNone(child, "free knot %d has no result child" % fi)
        shp = mc.listRelatives(goal, shapes=True, type="mesh",
                               fullPath=True) or []
        self.assertTrue(shp, "free knot %d goal has no visible icosahedron" % fi)
        bb = mc.exactWorldBoundingBox(shp[0])
        vc = [(bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2]
        cw = mc.xform(child, query=True, worldSpace=True, translation=True)
        self.assertLess(_mag([vc[j] - cw[j] for j in range(3)]), 0.5,
                        "visible icon did not track the solved knot "
                        "(worldspace blendShape not deforming)")


class DnetTwoKnotsDemoTest(unittest.TestCase):
    """The THIRD demo (``@maya_demo`` "Two Knots (Shapes)"): the MINIMAL dnet --
    TWO FREE knots plus FOUR anchors and FIVE links -- built with the SAME shape
    scheme (create_knot / create_link, draw_icon=True) as the layout demo. The two
    FREE knots (0, 1) are the moving hubs: knot 0 tethers to anchors 2, 3, knot 1
    to anchors 4, 5, and the two hubs link to each other. Each knot is a visible
    GOAL icosahedron worldspace-blendShaped onto a HIDDEN PROXY icosahedron shape
    on the RESULT child (which rides positions[i]); each knot owns an ``anchored``
    float wired into anchors[i]. Every link is a plain transform (its own
    ``tension``/``push``/``pull`` -> the solver, inheritsTransform OFF) parenting a
    degree-1 line whose 2 CVs track the two knots' RESULT children via a
    decomposeMatrix each. Run BY NAME through the wrapper's run_demo on a bare
    node."""

    _LN = 6                                     # knots (2 free + 4 anchors)
    _LE = 5                                     # links
    _FREE = [0, 1]                              # solver-driven hubs (anchors = 0)
    _ANCHORED = [2, 3, 4, 5]                    # pinned anchors (anchors = 1)
    # Rest-state link spans = initial knot separations: four spokes at sqrt(18)
    # and the free-hub -> free-hub link at 6.0 (positions ~ 0 -> children at goals).
    _EXPECTED_SPANS = sorted([18.0 ** 0.5] * 4 + [6.0])

    def setUp(self):
        mc.file(new=True, force=True)
        self.name = _create_vanilla(_REL)      # bare dnet: no demo run yet

    def test_shapes_demo_builds_icosahedron_net(self):
        from mpynode._common.util import log_bus

        # Run the THIRD demo by name. A crash mid-demo ships silently, so guard
        # the run with the log bus.
        sink = _ErrSink()
        log_bus.subscribe(sink)
        try:
            wrap_node(self.name).run_demo("demo_two_knots")
        finally:
            log_bus.unsubscribe(sink)
        self.assertFalse(sink.errors,
                         "shapes demo broadcast an error: %s" % sink.errors)

        n = self.name
        self.assertEqual(mc.getAttr(n + ".positions", size=True), self._LN,
                         "positions not sized to the 6 knots")
        self.assertEqual(mc.getAttr(n + ".index0", size=True), self._LE,
                         "index0 not sized to the 5 links")
        self.assertEqual(mc.getAttr(n + ".index1", size=True), self._LE,
                         "index1 not sized to the 5 links")

        # PURE SHAPES: no mPyLocator gizmos, no aim mPyTransforms anywhere.
        self.assertFalse(mc.ls(type="mPyLocator") or [],
                         "shapes demo must build NO mPyLocator gizmos")
        self.assertFalse(mc.ls(type="mPyTransform") or [],
                         "shapes demo must build NO aim mPyTransforms")

        # 6 visible GOAL icosahedra drive matrices[]; each is a poly mesh.
        goal_nodes = set(mc.listConnections(n + ".matrices", source=True,
                                            destination=False) or [])
        self.assertEqual(len(goal_nodes), self._LN,
                         "expected %d goal icosahedra on matrices[]" % self._LN)
        for g in goal_nodes:
            self.assertTrue(mc.listRelatives(g, shapes=True, type="mesh") or [],
                            "goal %s is not a polygon mesh" % g)

        # 6 RESULT children ride positions[] on .translate -- filtered by
        # destination plug so the fan-out to the curve decomposeMatrices is not
        # miscounted. Each is a mesh CHILD of its goal with a HIDDEN proxy shape.
        driven_plugs = (mc.listConnections(n + ".positions", source=False,
                                           destination=True, plugs=True) or [])
        children = set(p.rsplit(".", 1)[0] for p in driven_plugs
                       if p.rsplit(".", 1)[1] == "translate")
        self.assertEqual(len(children), self._LN,
                         "expected %d result children driven on .translate, got %d"
                         % (self._LN, len(children)))
        for c in children:
            parent = (mc.listRelatives(c, parent=True, fullPath=True)
                      or [None])[0]
            self.assertIsNotNone(parent, "child %s has no goal parent" % c)
            self.assertIn(parent.split("|")[-1], goal_nodes,
                          "child %s is not parented under a goal" % c)
            proxy = mc.listRelatives(c, shapes=True, type="mesh",
                                     fullPath=True) or []
            self.assertTrue(proxy, "child %s carries no proxy icosahedron" % c)
            self.assertFalse(mc.getAttr(proxy[0] + ".visibility"),
                             "proxy shape %s must be hidden" % proxy[0])

        # 6 worldspace blendShapes (proxy -> goal) at full weight.
        blends = mc.ls(type="blendShape") or []
        self.assertEqual(len(blends), self._LN,
                         "expected %d knot blendShapes, got %d"
                         % (self._LN, len(blends)))
        for bs in blends:
            self.assertAlmostEqual(mc.getAttr(bs + ".weight[0]"), 1.0, places=6,
                                   msg="blendShape %s not at full weight" % bs)

        # Anchoring partition: knots 2-5 pinned, free hubs 0-1 at 0. And every
        # anchors[i] is CONNECTED from the knot's `anchored` float, not setAttr.
        anchored = [i for i in range(self._LN)
                    if abs(mc.getAttr(n + ".anchors[%d]" % i)) >= 0.5]
        self.assertEqual(sorted(anchored), self._ANCHORED,
                         "anchors 2-5 must be pinned; hubs 0-1 free")
        for i in self._FREE:
            self.assertAlmostEqual(mc.getAttr(n + ".anchors[%d]" % i), 0.0,
                                   places=6,
                                   msg="free hub %d must have anchors = 0" % i)
        for i in range(self._LN):
            src = (mc.listConnections(n + ".anchors[%d]" % i, source=True,
                                      destination=False, plugs=True) or [None])[0]
            self.assertIsNotNone(src,
                                 "anchors[%d] must be driven by a knot attr" % i)
            self.assertEqual(src.rsplit(".", 1)[1], "anchored",
                             "anchors[%d] must be fed by the knot's `anchored` "
                             "float, got %s" % (i, src))

        # 5 link transforms each drive one tension slot via their own `tension`
        # attr (NOT an aim translateX) and parent exactly one degree-1 curve whose
        # 2 CVs track the knots' RESULT children (a decomposeMatrix per CV --
        # world positions, NOT the goal-local positions[]).
        tension_plugs = (mc.listConnections(n + ".tension", source=True,
                                            destination=False, plugs=True) or [])
        self.assertEqual(len(tension_plugs), self._LE,
                         "expected %d tension[e] slots wired" % self._LE)
        self.assertTrue(all(p.split(".", 1)[1] == "tension"
                            for p in tension_plugs),
                        "tension must be driven by the links' own `tension` attr, "
                        "got %s" % tension_plugs)
        links = _link_nodes(n)
        self.assertEqual(len(links), self._LE,
                         "expected %d link transforms, got %s" % (self._LE, links))
        spans = []
        for link in links:
            self.assertEqual(mc.getAttr(link + ".inheritsTransform"), 0,
                             "link %s must have inheritsTransform OFF" % link)
            # SRT + visibility locked and hidden -> only tension/push/pull show.
            for chan in ("tx", "ty", "tz", "rx", "ry", "rz",
                         "sx", "sy", "sz", "v"):
                a = "%s.%s" % (link, chan)
                self.assertTrue(mc.getAttr(a, lock=True),
                                "%s must be locked" % a)
                self.assertFalse(mc.getAttr(a, keyable=True),
                                 "%s must be non-keyable (hidden)" % a)
                self.assertFalse(mc.getAttr(a, channelBox=True),
                                 "%s must be hidden from the channel box" % a)
            curves = mc.listRelatives(link, shapes=True, type="nurbsCurve",
                                      fullPath=True) or []
            self.assertEqual(len(curves), 1,
                             "link %s must parent exactly ONE line curve" % link)
            crv = curves[0]
            self.assertEqual(mc.getAttr(crv + ".degree"), 1,
                             "link curve %s must be linear (degree 1)" % crv)
            ncv = len(mc.ls(crv + ".cv[*]", flatten=True) or [])
            self.assertEqual(ncv, 2, "link curve %s must have 2 CVs" % crv)
            # CVs read a decomposeMatrix (the child's WORLD position), never
            # positions[] -- that is goal-local and would collapse the curve.
            for cv in (0, 1):
                src = mc.listConnections(crv + ".controlPoints[%d]" % cv,
                                         source=True, destination=False,
                                         plugs=True) or []
                self.assertTrue(src,
                                "curve %s cv %d not driven: %s" % (crv, cv, src))
                self.assertTrue(
                    any(mc.nodeType(p.rsplit(".", 1)[0]) == "decomposeMatrix"
                        for p in src),
                    "curve %s cv %d must be driven by a decomposeMatrix: %s"
                    % (crv, cv, src))
                self.assertFalse(any(".positions" in p for p in src),
                                 "curve %s cv %d must NOT read positions[]: %s"
                                 % (crv, cv, src))
            # The segment must SPAN its two knots, not collapse.
            c0 = mc.pointPosition(crv + ".cv[0]", world=True)
            c1 = mc.pointPosition(crv + ".cv[1]", world=True)
            span = _mag([c1[j] - c0[j] for j in range(3)])
            self.assertGreater(span, 1.0,
                               "link curve %s is degenerate (span=%.4f)"
                               % (crv, span))
            spans.append(span)
        # At rest positions ~0, so the spans equal the initial knot separations.
        for got, want in zip(sorted(spans), self._EXPECTED_SPANS):
            self.assertAlmostEqual(got, want, delta=0.2,
                                   msg="link spans %s do not match the layout %s"
                                       % (sorted(spans), self._EXPECTED_SPANS))

    def test_shapes_demo_free_hubs_follow_when_anchor_dragged(self):
        # The two FREE hubs start at equilibrium (positions ~ 0). Dragging an
        # ANCHOR must pull its free hub off equilibrium while the anchor itself
        # stays pinned. resetBuffer forces a fresh full solve each eval, so the
        # read is the settled state.
        from mpynode._common.util import log_bus

        wrap_node(self.name).run_demo("demo_two_knots")
        n = self.name
        self.assertEqual(len(_link_nodes(n)), self._LE,
                         "expected %d link transforms" % self._LE)

        mc.setAttr(n + ".resetBuffer", 1)

        def driven_mag(i):
            mc.dgdirty(n + ".positions")
            return _mag(mc.getAttr(n + ".positions[%d]" % i)[0])

        sink = _ErrSink()
        log_bus.subscribe(sink)
        try:
            # Precondition: knots 0,1 free (anchors 0), 2-5 pinned (anchors 1).
            for i in self._FREE:
                self.assertEqual(mc.getAttr(n + ".anchors[%d]" % i), 0.0,
                                 "hub %d must be free (anchors = 0)" % i)
            for i in self._ANCHORED:
                self.assertEqual(mc.getAttr(n + ".anchors[%d]" % i), 1.0,
                                 "knot %d must be pinned (anchors = 1)" % i)

            rest0 = driven_mag(0)                       # free hub at rest -> ~0

            # Drag anchor 2's goal (a spoke of hub 0) well away; hub 0 must follow.
            g2 = (mc.listConnections(n + ".matrices[2]", source=True,
                                     destination=False) or [None])[0]
            self.assertIsNotNone(g2, "anchor 2 goal not wired to matrices[2]")
            mc.move(8.0, 5.0, 3.0, g2, relative=True)

            after0 = driven_mag(0)                      # free hub follows -> grows
            after2 = driven_mag(2)                      # anchor still pinned -> ~0
        finally:
            log_bus.unsubscribe(sink)

        self.assertFalse(sink.errors,
                         "two-knot net errored: %s" % sink.errors)
        self.assertLess(rest0, 1e-2,
                        "free hub 0 should sit at equilibrium (positions ~ 0)")
        self.assertGreater(after0, 0.2,
                           "dragging anchor 2 must pull free hub 0 off "
                           "equilibrium (positions grows), got %.4f" % after0)
        self.assertLess(after2, 1e-2,
                        "dragged anchor 2 must stay pinned (positions ~ 0), got "
                        "%.4f" % after2)


class DnetAuthoringTest(unittest.TestCase):
    """The create_knot / create_link Methods commands: the by-hand authoring
    path a user drives to build a network (no demo). These prove the commands
    are invocable through the real wrapper.call_command surface and that they
    lay down the exact node wiring the solver reads."""

    def setUp(self):
        mc.file(new=True, force=True)
        self.name = _create_vanilla(_REL)
        self.w = wrap_node(self.name)

    def _knot(self, x, y, z, draw_icon=False):
        goal = self.w.call_command("dnetCreateKnot", draw_icon=draw_icon)
        mc.setAttr(goal + ".translate", x, y, z, type="double3")
        return goal

    def test_create_knot_wires_goal_matrix_and_anchor(self):
        knots = [self._knot(*p) for p in [(0, 0, 0), (2, 0, 0), (1, 2, 0)]]
        # dense knot slots 0,1,2 in creation order; each goal carries `anchored`,
        # drives matrices[i] + anchors[i], and has a child riding positions[i].
        for i, k in enumerate(knots):
            self.assertTrue(mc.objExists(k + ".anchored"),
                            "%s has no anchored attr" % k)
            m = mc.listConnections(k + ".worldMatrix[0]", source=False,
                                   destination=True, plugs=True) or []
            self.assertTrue(any(p.endswith(".matrices[%d]" % i) for p in m),
                            "knot %d worldMatrix not wired to matrices[%d]: %s"
                            % (i, i, m))
            a = mc.listConnections(k + ".anchored", source=False,
                                   destination=True, plugs=True) or []
            self.assertTrue(any(p.endswith(".anchors[%d]" % i) for p in a),
                            "knot %d anchored not wired to anchors[%d]: %s"
                            % (i, i, a))
            child = None
            for c in (mc.listRelatives(k, children=True, type="transform",
                                       fullPath=True) or []):
                conns = mc.listConnections(c + ".translate", source=True,
                                           destination=False, plugs=True) or []
                if any(p.endswith(".positions[%d]" % i) for p in conns):
                    child = c
            self.assertIsNotNone(child,
                                 "knot %d has no child riding positions[%d]"
                                 % (i, i))
        # create_knot leaves the newest knot selected (chainable into a link).
        self.assertEqual(mc.ls(selection=True, long=True),
                         mc.ls(knots[-1], long=True))

    def test_create_knot_draw_icon_builds_icosahedron_proxy(self):
        # draw_icon=True: a `radius` attr drives BOTH icosahedra -- visible on the
        # goal, hidden PROXY on the RESULT child -- joined by a worldspace
        # blendShape (proxy -> visible).
        goal = self._knot(0, 0, 0, draw_icon=True)
        self.assertTrue(mc.objExists(goal + ".radius"),
                        "draw_icon knot has no radius attr")
        # visible icosahedron mesh on the goal.
        vis = mc.listRelatives(goal, shapes=True, type="mesh",
                               fullPath=True) or []
        self.assertTrue(vis, "goal has no visible icosahedron mesh")
        self.assertTrue(mc.getAttr(vis[0] + ".visibility"),
                        "goal icosahedron must be visible")
        # hidden proxy mesh on the RESULT child.
        child = (mc.listRelatives(goal, children=True, type="transform",
                                  fullPath=True) or [None])[0]
        self.assertIsNotNone(child, "draw_icon knot has no result child")
        proxy = mc.listRelatives(child, shapes=True, type="mesh",
                                 fullPath=True) or []
        self.assertTrue(proxy, "result child has no proxy icosahedron mesh")
        self.assertFalse(mc.getAttr(proxy[0] + ".visibility"),
                         "proxy icosahedron must be hidden")
        # the icon size defaults to 0.1 (unset radius).
        self.assertAlmostEqual(mc.getAttr(goal + ".radius"), 0.1, places=6,
                               msg="default icon radius should be 0.1")
        # radius drives both platonic-solid creators.
        creators = mc.listConnections(goal + ".radius", source=False,
                                      destination=True) or []
        types = set(mc.nodeType(c) for c in creators)
        self.assertIn("polyPlatonicSolid", types,
                      "radius must drive polyPlatonicSolid creators, got %s"
                      % types)
        # worldspace blendShape links proxy -> visible at full weight.
        blends = mc.ls(type="blendShape") or []
        self.assertEqual(len(blends), 1, "expected one knot blendShape")
        self.assertAlmostEqual(mc.getAttr(blends[0] + ".weight[0]"), 1.0,
                               places=6, msg="knot blendShape not at full weight")

    def test_create_link_builds_springs_curves_and_per_link_tension_push_pull(self):
        # four knots; link spokes 0,1,2 -> hub 3 (hub selected LAST). draw_icon
        # True so each link parents a line whose CVs track the knot children.
        knots = [self._knot(*p) for p in
                 [(0, 0, 0), (3, 0, 0), (0, 3, 0), (0, 0, 3)]]
        mc.select(knots[0], replace=True)
        for k in knots[1:]:
            mc.select(k, add=True)                    # hub (knots[3]) ends last
        links = self.w.call_command("dnetCreateLink", draw_icon=True)

        self.assertEqual(len(links), 3, "expected one link transform per spoke")
        self.assertEqual(mc.getAttr(self.name + ".index0", size=True), 3)
        i0 = [mc.getAttr(self.name + ".index0[%d]" % e) for e in range(3)]
        i1 = [mc.getAttr(self.name + ".index1[%d]" % e) for e in range(3)]
        self.assertEqual(i0, [0, 1, 2], "index0 must be the spoke indices")
        self.assertEqual(i1, [3, 3, 3], "index1 must be the hub index")

        # rest lengths = creation distances: 3, then sqrt(18) twice. Distances
        # are translation-invariant, so these are exact wherever the rig sits.
        rest = [mc.getAttr(self.name + ".restLengths[%d]" % e)
                for e in range(3)]
        self.assertAlmostEqual(rest[0], 3.0, places=4)
        self.assertAlmostEqual(rest[1], 18.0 ** 0.5, places=4)
        self.assertAlmostEqual(rest[2], 18.0 ** 0.5, places=4)

        for e, link in enumerate(links):
            # inheritsTransform OFF keeps the world-space line from being
            # double-transformed.
            self.assertEqual(mc.getAttr(link + ".inheritsTransform"), 0,
                             "link %d must have inheritsTransform OFF" % e)
            # SRT + visibility LOCKED and HIDDEN; only tension/push/pull show.
            for chan in ("tx", "ty", "tz", "rx", "ry", "rz",
                         "sx", "sy", "sz", "v"):
                a = "%s.%s" % (link, chan)
                self.assertTrue(mc.getAttr(a, lock=True),
                                "%s must be locked" % a)
                self.assertFalse(mc.getAttr(a, keyable=True),
                                 "%s must be non-keyable (hidden)" % a)
                self.assertFalse(mc.getAttr(a, channelBox=True),
                                 "%s must be hidden from the channel box" % a)
            for attr in ("tension", "push", "pull"):
                self.assertTrue(mc.getAttr("%s.%s" % (link, attr), keyable=True),
                                "link %d %s must stay keyable/visible" % (e, attr))
            shp = mc.listRelatives(link, shapes=True, type="nurbsCurve",
                                   fullPath=True)[0]
            self.assertEqual(mc.getAttr(shp + ".degree"), 1,
                             "link curve must be linear (degree 1)")
            ncv = len(mc.ls(shp + ".cv[*]", flatten=True) or [])
            self.assertEqual(ncv, 2, "linear link curve must have 2 CVs")
            for cv in (0, 1):
                src = mc.listConnections(shp + ".controlPoints[%d]" % cv,
                                         source=True, destination=False,
                                         plugs=True) or []
                self.assertTrue(
                    any(mc.nodeType(p.rsplit(".", 1)[0]) == "decomposeMatrix"
                        for p in src),
                    "cv %d not driven by a decomposeMatrix: %s" % (cv, src))
                self.assertFalse(any(".positions" in p for p in src),
                                 "cv %d must NOT read the goal-local positions[]: "
                                 "%s" % (cv, src))
            # Each link's own tension/push/pull is wired to its per-link slot.
            for attr, dflt in (("tension", 0.0), ("push", 1.0), ("pull", 1.0)):
                self.assertTrue(mc.objExists("%s.%s" % (link, attr)),
                                "%s has no %s attr" % (link, attr))
                self.assertAlmostEqual(mc.getAttr("%s.%s" % (link, attr)), dflt,
                                       places=4,
                                       msg="%s.%s default should be %s"
                                       % (link, attr, dflt))
                wired = mc.listConnections("%s.%s" % (link, attr), source=False,
                                           destination=True, plugs=True) or []
                self.assertTrue(
                    any(p.endswith(".%s[%d]" % (attr, e)) for p in wired),
                    "link %d %s not wired to %s[%d]: %s"
                    % (e, attr, attr, e, wired))

    def test_authored_network_solves_with_anchored_hub(self):
        # A hand-built star: hub anchored, spokes free. A free spoke must move
        # toward the hub when tension is raised -- proving the authored wiring
        # actually solves.
        from mpynode._common.util import log_bus

        knots = [self._knot(*p) for p in
                 [(5, 0, 0), (-5, 0, 0), (0, 5, 0), (0, 0, 0)]]
        mc.select(knots[0], replace=True)
        for k in knots[1:]:
            mc.select(k, add=True)                    # hub (origin) last
        links = self.w.call_command("dnetCreateLink")
        mc.setAttr(knots[3] + ".anchored", 1.0)       # pin the hub
        mc.setAttr(self.name + ".resetBuffer", 1)
        mc.setAttr(self.name + ".iterations", 300)

        def spoke0_disp():
            mc.dgdirty(self.name + ".positions")
            return _mag(mc.getAttr(self.name + ".positions[0]")[0])

        sink = _ErrSink()
        log_bus.subscribe(sink)
        try:
            slack = spoke0_disp()                      # no tension -> at rest
            for link in links:
                mc.setAttr(link + ".tension", 1.0)    # contract every link
            taut = spoke0_disp()
        finally:
            log_bus.unsubscribe(sink)

        self.assertFalse(sink.errors,
                         "authored network broadcast an error: %s" % sink.errors)
        self.assertLess(slack, 1e-2,
                        "free spoke should sit at its rest length with no tension")
        self.assertGreater(taut, 0.05,
                           "raising a link's tension did not move its free spoke")

    def test_per_link_push_pull_scale_the_kernel_restoring_force(self):
        # Red-green for the PER-LINK `push` / `pull` arrays create_link wires.
        # push scales the restoring force when a link is COMPRESSED (current <
        # rest), pull when it is STRETCHED; 0 kills that force, 1 restores it. The
        # spoke moving only when the relevant knob is on can happen only if
        # push[e]/pull[e] actually reach the kernel.
        from mpynode._common.util import log_bus

        spoke = self._knot(5, 0, 0)                    # free spoke
        hub = self._knot(0, 0, 0)                      # hub -> anchored
        mc.select(spoke, replace=True)
        mc.select(hub, add=True)                       # hub selected last
        links = self.w.call_command("dnetCreateLink")
        link = links[0]
        mc.setAttr(hub + ".anchored", 1.0)            # pin the hub at origin
        mc.setAttr(self.name + ".resetBuffer", 1)     # re-seed from goals each eval
        mc.setAttr(self.name + ".iterations", 300)

        def spoke_disp():
            mc.dgdirty(self.name + ".positions")
            return _mag(mc.getAttr(self.name + ".positions[0]")[0])

        sink = _ErrSink()
        log_bus.subscribe(sink)
        try:
            # --- STRETCH the link (rest < creation length 5) -> pull governs. ---
            mc.setAttr(self.name + ".restLengths[0]", 2.0)
            mc.setAttr(link + ".push", 1.0)
            mc.setAttr(link + ".pull", 0.0)           # no pull -> spoke stays put
            pull_off = spoke_disp()
            mc.setAttr(link + ".pull", 1.0)           # pull on -> spoke drawn in
            pull_on = spoke_disp()

            # --- COMPRESS the link (rest > creation length 5) -> push governs. ---
            mc.setAttr(self.name + ".restLengths[0]", 9.0)
            mc.setAttr(link + ".pull", 1.0)
            mc.setAttr(link + ".push", 0.0)           # no push -> spoke stays put
            push_off = spoke_disp()
            mc.setAttr(link + ".push", 1.0)           # push on -> spoke shoved out
            push_on = spoke_disp()
        finally:
            log_bus.unsubscribe(sink)

        self.assertFalse(sink.errors,
                         "push/pull sweep broadcast an error: %s" % sink.errors)
        self.assertLess(pull_off, 1e-2,
                        "pull=0 on a STRETCHED link should leave the spoke at its "
                        "goal (pull[e] not reaching the kernel?): %.4f" % pull_off)
        self.assertGreater(pull_on, pull_off + 0.05,
                           "pull=1 did not draw the free spoke in on a stretched "
                           "link (per-link pull dropped?): off=%.4f on=%.4f"
                           % (pull_off, pull_on))
        self.assertLess(push_off, 1e-2,
                        "push=0 on a COMPRESSED link should leave the spoke at its "
                        "goal (push[e] not reaching the kernel?): %.4f" % push_off)
        self.assertGreater(push_on, push_off + 0.05,
                           "push=1 did not shove the free spoke out on a compressed "
                           "link (per-link push dropped?): off=%.4f on=%.4f"
                           % (push_off, push_on))


class DnetSolverModuleTest(unittest.TestCase):
    """The relaxation Solver now lives in
    ``mpynode._common.nodes.rigging.dnet`` (imported by the node's Init/Compute),
    so it can be exercised DIRECTLY -- no template, no node graph, no dnet plug-in.
    That direct testability is the whole point of the extraction, so prove it: a
    tiny 3-knot chain with both ends anchored and a free middle knot pulled off
    the line must relax the middle back onto the segment while the anchors stay
    pinned. (This runs under mayapy like the rest of the module, but touches only
    numpy + the Solver -- not maya.cmds.)"""

    def test_solver_relaxes_free_knot_between_anchors(self):
        import numpy as np
        from mpynode._common.nodes.rigging.dnet import (
            Solver, create_knot, create_link)

        # helpers must be importable as plain callables (used by the shims).
        self.assertTrue(callable(create_knot) and callable(create_link),
                        "authoring helpers must be importable from the module")

        def mat(x, y=0.0, z=0.0):
            m = np.identity(4)
            m[3, 0], m[3, 1], m[3, 2] = x, y, z
            return m

        # ends at x=0/x=20 anchored, middle's goal lifted OFF the line to y=8.
        # Two links of rest length 5 -> both stretched, pulling the middle down.
        matrices = np.array([mat(0.0), mat(10.0, 8.0), mat(20.0)])
        anchors = np.array([1.0, 0.0, 1.0])
        index0 = np.array([0, 1], dtype=np.int32)
        index1 = np.array([1, 2], dtype=np.int32)
        lengths = np.array([5.0, 5.0])

        solver = Solver(None)
        solver.evaluate(matrices, anchors, lengths, index0=index0, index1=index1,
                        iterations=300, tolerance=1e-6, damping=0.2)
        pos = np.asarray(solver.positions)      # world solved positions (3, 3)

        # anchored ends snap to their goals.
        self.assertAlmostEqual(float(pos[0, 0]), 0.0, places=3,
                               msg="anchored end 0 drifted")
        self.assertAlmostEqual(float(pos[2, 0]), 20.0, places=3,
                               msg="anchored end 2 drifted")
        # the free middle relaxed off its lifted goal, back down toward the line.
        self.assertLess(float(pos[1, 1]), 7.5,
                        "free middle knot did not relax toward the segment")
        # and it stays roughly centred in X (symmetric pull) -- not collapsed.
        self.assertLess(abs(float(pos[1, 0]) - 10.0), 2.0,
                        "free middle knot drifted off-centre in X")
        # max_force is the last iteration's tolerance^2 displacement, so a
        # converged solve reports it non-negative and small.
        self.assertGreaterEqual(float(solver.max_force), 0.0)


if __name__ == "__main__":
    unittest.main()
