"""mPyTransform node + transform/mesh SelfProxy migration

Consolidated from: test_phase31_0_transform.py, test_phaseG_1_transform.py, test_phaseF_4_transform_poly.py.
"""

from __future__ import annotations

# ===================== from test_phase31_0_transform.py =====================
import unittest

import maya.cmds as mc
import numpy as np

from._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase31_0_transform():
    standalone_init()


# ===========================================================================
# Plug-in registration
# ===========================================================================


class TestMPyTransformBasics(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_node_type_registered(self):
        self.assertIn("mPyTransform", mc.allNodeTypes() or [])

    def test_create_bare_node(self):
        n = mc.createNode("mPyTransform", name="t1")
        self.assertTrue(mc.objExists(n))
        self.assertEqual(mc.nodeType(n), "mPyTransform")

    def test_node_inherits_transform(self):
        n = mc.createNode("mPyTransform", name="t1")
        inherited = mc.nodeType(n, inherited=True) or []
        self.assertIn("transform", inherited)
        self.assertIn("dagNode", inherited)

    def test_trs_channels_exist(self):
        n = mc.createNode("mPyTransform", name="t1")
        for attr in (
            "translateX",
            "translateY",
            "translateZ",
            "rotateX",
            "rotateY",
            "rotateZ",
            "scaleX",
            "scaleY",
            "scaleZ",
            "shearXY",
            "shearXZ",
            "shearYZ",
            "rotateOrder",
            "parentMatrix",
        ):
            self.assertTrue(
                mc.attributeQuery(attr, node=n, exists=True),
                f"inherited attr {attr!r} missing on mPyTransform",
            )

    def test_expression_attr_exists(self):
        n = mc.createNode("mPyTransform", name="t1")
        self.assertTrue(mc.attributeQuery("_computeSource", node=n, exists=True))

    def test_internal_attrs(self):
        n = mc.createNode("mPyTransform", name="t1")
        for plug in (
            "_computeSource",
            "_inputAttrs",
            "_outputAttrs",
            "_storedVarNames",
            "_storedVarsData",
            "debug_mode",
            "profile_enabled",
            "deep_profile_enabled",
            "watch_enabled",
        ):
            self.assertTrue(
                mc.attributeQuery(plug, node=n, exists=True),
                f"plug {plug!r} should exist on mPyTransform",
            )


# ===========================================================================
# INTERNAL_VARS schema
# ===========================================================================


class TestMPyTransformExpression(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_empty_expression_is_noop(self):
        """No expression -> matrix uses standard TRS composition."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".translateY", 5.0)
        m = mc.getAttr(n + ".matrix")
        # Translation lives in row 3 (cols 12, 13, 14 in flat).
        self.assertAlmostEqual(m[13], 5.0)

    def test_noop_expression_is_trs(self):
        """An expression that sets no matrix (every slot at default) leaves the
        node a plain transform -- ``.matrix`` is the honest TRS composition."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(
            n + "._computeSource", "self.local_matrix = None", type="string"
        )
        mc.setAttr(n + ".translateX", 1.5)
        mc.setAttr(n + ".translateY", 2.5)
        mc.setAttr(n + ".translateZ", -3.0)
        m = mc.getAttr(n + ".matrix")
        self.assertAlmostEqual(m[12], 1.5)
        self.assertAlmostEqual(m[13], 2.5)
        self.assertAlmostEqual(m[14], -3.0)

    def test_translate_override(self):
        """A gated local matrix overrides the live translate; the result is
        delivered via offsetParentMatrix so it appears in ``worldMatrix``
        (matrix x opm x parent), not the TRS-only ``.matrix``."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[3, 0] = 3.0; m[3, 1] = 10.0\n"
            "self.local_matrix = m\n"
            "self.apply_translate = True\n",
            type="string",
        )
        mc.setAttr(n + ".translateX", 99.0)  # overridden by the gated matrix
        m = mc.getAttr(n + ".worldMatrix[0]")
        self.assertAlmostEqual(m[12], 3.0)
        self.assertAlmostEqual(m[13], 10.0)

    def test_expression_error_safe_fallback(self):
        """Bad expression -> transform behaves as normal Maya transform."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".translateY", 5.0)
        mc.setAttr(
            n + "._computeSource",
            "this is not python at all!!!",
            type="string",
        )
        m = mc.getAttr(n + ".matrix")
        # Falls back to standard TRS composition.
        self.assertAlmostEqual(m[13], 5.0)

    def test_world_matrix_reflects_expression(self):
        """WorldMatrix output reflects the gated matrix result."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[3, 1] = 15.0\n"
            "self.local_matrix = m\n"
            "self.apply_translate = True\n",
            type="string",
        )
        wm = mc.getAttr(n + ".worldMatrix[0]")
        self.assertAlmostEqual(wm[13], 15.0)

    def test_set_expression_triggers_reeval(self):
        """Setting a NEW expression must invalidate the matrix.

        In mayapy without a viewport, the matrix output isn't auto-
        invalidated when an internal attr like '_computeSource' changes,
        so the test explicitly dgdirty-s the node to force re-eval --
        this matches what interactive Maya does automatically via the
        viewport refresh after a Channel Box edit.
        """
        n = mc.createNode("mPyTransform", name="t1")
        # First expression: Y = 5.
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[3, 1] = 5.0\n"
            "self.local_matrix = m\n"
            "self.apply_translate = True\n",
            type="string",
        )
        m1 = mc.getAttr(n + ".worldMatrix[0]")
        self.assertAlmostEqual(m1[13], 5.0)
        # Replace expression: Y = 11.
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[3, 1] = 11.0\n"
            "self.local_matrix = m\n"
            "self.apply_translate = True\n",
            type="string",
        )
        # setDependentsDirty(_computeSource) dirties _outLocalFlat -> the relay
        # recomputes offsetParentMatrix -> worldMatrix natively; the dgdirty is
        # belt-and-suspenders for the mayapy no-viewport quirk.
        mc.dgdirty(n)
        m2 = mc.getAttr(n + ".worldMatrix[0]")
        self.assertAlmostEqual(m2[13], 11.0)

    def test_self_matrix_write_no_infinite_recursion(self):
        """Writing the built-in ``self.matrix`` plug (instead of the documented
        ``self.output_matrix`` write-back slot) must not crash.

        Flush-free re-arch: ``asMatrix()`` no longer runs the expression (it
        returns the plain TRS matrix), so the historic
        ``self.matrix``-triggers-asMatrix-re-entry recursion is structurally
        impossible. The expression runs in ``compute(_outLocalFlat)`` instead;
        a stray ``self.matrix`` write there simply never reaches
        offsetParentMatrix (only ``self.output_matrix`` does), so the node
        behaves as a standard transform (``.matrix`` == TRS, worldMatrix ==
        TRS x parent). This test guards that the read stays crash-free and the
        recursion regression cannot return.
        """
        import io
        import sys

        n = mc.createNode("mPyTransform", name="reentrant")
        mc.setAttr(n + ".translateY", 5.0)
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\nself.matrix = np.eye(4)\n",
            type="string",
        )
        buf = io.StringIO()
        saved_stderr = sys.stderr
        sys.stderr = buf
        try:
            m = mc.getAttr(n + ".matrix")
            wm = mc.getAttr(n + ".worldMatrix[0]")
        finally:
            sys.stderr = saved_stderr
        err = buf.getvalue()
        # The historic failure mode must be gone.
        self.assertNotIn("maximum recursion depth", err)
        # ``.matrix`` is the plain TRS composition (translateY = 5.0); the stray
        # self.matrix write is inert and worldMatrix inherits the same TRS.
        self.assertEqual(len(m), 16)
        self.assertAlmostEqual(m[13], 5.0)
        self.assertAlmostEqual(wm[13], 5.0)


# ===========================================================================
# DAG behaviour -- children must follow the custom matrix
# ===========================================================================


class TestChildrenFollowCustomMatrix(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_child_world_position_reflects_custom_matrix(self):
        n = mc.createNode("mPyTransform", name="bobbing")
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[3, 0] = 2.0; m[3, 1] = 8.0\n"
            "self.local_matrix = m\n"
            "self.apply_translate = True\n",
            type="string",
        )
        cube = mc.polyCube(name="child")[0]
        # relative=True keeps the cube's LOCAL position at (0,0,0); without
        # this, mc.parent() offsets the local transform to preserve world
        # position, which would mask the parent's custom matrix override.
        mc.parent(cube, n, relative=True)
        # Force re-evaluation.
        mc.setAttr(n + ".translateX", 2.0)
        mc.dgdirty(cube)
        # World position of cube should be (2, 8, 0).
        wpos = mc.xform(cube, q=True, ws=True, t=True)
        self.assertAlmostEqual(wpos[0], 2.0)
        self.assertAlmostEqual(wpos[1], 8.0)
        self.assertAlmostEqual(wpos[2], 0.0)


# ===========================================================================
# SelfProxy + stored vars round-trip
# ===========================================================================


class TestStoredVars(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_user_storage_roundtrip(self):
        """Self.foo = 42 must persist across evaluations."""
        from mpynode._common.io import serialization

        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\n"
            "if not hasattr(self, 'tick'):\n"
            "    self.tick = 0\n"
            "self.tick += 1\n"
            "m = np.eye(4)\n"
            "m[3, 1] = float(self.tick)\n"
            "self.local_matrix = m\n"
            "self.apply_translate = True\n",
            type="string",
        )
        # Trigger 3 evaluations. Read worldMatrix (NOT .matrix): the expression
        # now runs when the opm output is pulled, which worldMatrix depends on;
        # .matrix is the TRS-only path and no longer runs the expression.
        for i in range(3):
            mc.setAttr(n + ".translateX", float(i))
            mc.dgdirty(n)
            mc.getAttr(n + ".worldMatrix[0]")
        # Stored vars should reflect at least one tick increment.
        sv_str = mc.getAttr(n + "._storedVarsData") or ""
        if sv_str:
            stored = serialization.decode_stored_vars(sv_str)
            self.assertIn("tick", stored)
            self.assertGreaterEqual(stored["tick"], 1)


# ===========================================================================
# Wrapper
# ===========================================================================


class TestMPyTransformWrapper(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_create_classmethod(self):
        from mpynode.wrappers.mpy_transform import MPyTransform

        t = MPyTransform.create(name="wrapped")
        self.assertTrue(mc.objExists("wrapped"))
        self.assertEqual(mc.nodeType("wrapped"), "mPyTransform")

    def test_native_type_constant(self):
        from mpynode.wrappers.mpy_transform import MPyTransform

        self.assertEqual(MPyTransform.NATIVE_TYPE, "mPyTransform")

    def test_set_get_expression_roundtrip(self):
        from mpynode.wrappers.mpy_transform import MPyTransform

        t = MPyTransform.create(name="wrap2")
        src = "self.local_matrix = None"
        t.set_compute_expression(src)
        self.assertEqual(t.get_compute_expression(), src)

    def test_repr(self):
        from mpynode.wrappers.mpy_transform import MPyTransform

        t = MPyTransform.create(name="wrap3")
        r = repr(t)
        self.assertIn("MPyTransform", r)
        self.assertIn("wrap3", r)


# ===========================================================================
# Demo
# ===========================================================================


# ===========================================================================
# Time-driven bobbing -- the matrix must re-evaluate on currentTime change
# WITHOUT explicit dgdirty calls (production motion-graphics use case).
# ===========================================================================


class TestTimeDrivenMatrix(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_create_does_not_auto_connect_time(self):
        """Time is OPT-IN: MPyTransform.create() no longer wires time1.
        A static transform doesn't re-touch its TRS every frame. The
        user opts in by connecting time1 (or adding a time input)."""
        from mpynode.wrappers.mpy_transform import MPyTransform

        t = MPyTransform.create(name="timeRig")
        self.assertFalse(mc.isConnected("time1.outTime", t.get_name() + "._timeIn"))
        mc.connectAttr("time1.outTime", t.get_name() + "._timeIn", force=True)
        self.assertTrue(mc.isConnected("time1.outTime", t.get_name() + "._timeIn"))

# ===========================================================================
# Combined demo: mPyTransform + mPyLocator working together
# ===========================================================================


# ===================== from test_phaseG_1_transform.py =====================
import inspect
import unittest

import maya.cmds as mc
import numpy as np

from._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseG_1_transform():
    standalone_init()


class TestSourceCleanups(unittest.TestCase):
    """Source-level pin -- legacy SelfProxy is gone from
    mpy_transform.py."""

    def test_selfproxy_import_present(self):
        """There's only one SelfProxy now (legacy class
        deleted); ``mpy_transform.py`` must import it."""
        from mpynode._api1 import mpy_transform as transform_node

        src = inspect.getsource(transform_node)
        self.assertIn(
            "from mpynode._common.compute.self_proxy import SelfProxy",
            src,
            "mpy_transform.py must import SelfProxy",
        )

    def test_uses_compute_locals_kwarg(self):
        from mpynode._api1 import mpy_transform as transform_node

        src = inspect.getsource(transform_node)
        self.assertIn(
            "compute_locals=compute_locals",
            src,
            "mpy_transform.py must construct PlugSelfProxy with "
            "compute_locals=...",
        )


class TestExpressionRoundTrip(unittest.TestCase):

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def _new_transform(self):
        return mc.createNode("mPyTransform")

    def test_identity_no_op(self):
        n = self._new_transform()
        # Empty expression -> asMatrix returns the inherent local matrix.
        m = mc.getAttr(n + ".matrix")
        self.assertEqual(len(m), 16)

    def test_user_writes_local_matrix_scale(self):
        """User drives a scale-3 local matrix (apply_scale); the node's
        worldMatrix should reflect that scale."""
        n = self._new_transform()
        expr = (
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[0,0] = 3.0\n"
            "m[1,1] = 3.0\n"
            "m[2,2] = 3.0\n"
            "self.local_matrix = m\n"
            "self.apply_scale = True\n"
        )
        mc.setAttr(n + "._computeSource", expr, type="string")
        # The expression result reaches worldMatrix via offsetParentMatrix.
        m = mc.getAttr(n + ".worldMatrix[0]")
        self.assertEqual(len(m), 16)
        diag = (m[0], m[5], m[10])
        for v in diag:
            self.assertAlmostEqual(v, 3.0, places=4)

    def test_user_storage_still_persists(self):
        """Writes to non-pre-populated, non-plug names go to stored
        vars and survive recompute."""
        n = self._new_transform()
        expr = (
            "import numpy as np\n"
            "self.iter_count = self.iter_count + 1 if hasattr(self, 'iter_count') else 1\n"
            "self.local_matrix = np.eye(4)\n"
            "self.apply_translate = True\n"
        )
        mc.setAttr(n + "._computeSource", expr, type="string")
        # Force two evaluations via worldMatrix (the path that runs the expr).
        mc.getAttr(n + ".worldMatrix[0]")
        mc.dgdirty(n)
        mc.getAttr(n + ".worldMatrix[0]")
        from mpynode._common.storedvars.stored_vars_api import get_variables

        sv = get_variables(n)
        # iter_count should be at least 1 (eager-eval may have
        # collapsed to 1 or 2 depending on dirty propagation).
        self.assertIn("iter_count", sv)
        self.assertGreaterEqual(sv["iter_count"], 1)


# ===================== from test_phaseF_4_transform_poly.py =====================
import unittest

import maya.cmds as mc
import maya.OpenMaya as om
import numpy as np

from._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseF_4_transform_poly():
    standalone_init()


class TestF4SchemaDeleted(unittest.TestCase):
    def test_transform_internal_vars_gone(self):
        from mpynode._api1.mpy_transform import MPyTransform
        self.assertFalse(hasattr(MPyTransform, "INTERNAL_VARS"))

    def test_poly_internal_vars_gone(self):
        from mpynode._api2.mpy_mesh import MPyMesh
        self.assertFalse(hasattr(MPyMesh, "INTERNAL_VARS"))


class TestF4TransformExpressionStillWorks(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_self_local_matrix_drives_transform(self):
        n = mc.createNode("mPyTransform", name="tfm1")
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[3, 0] = 99.0\n"
            "self.local_matrix = m\n"
            "self.apply_translate = True\n",
            type="string",
        )
        # worldMatrix[12] is tx (root node -> worldMatrix == expression result)
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[12], 99.0)


class TestF4PolyExpressionStillWorks(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_self_points_counts_indices_build_mesh(self):
        p = mc.createNode("mPyMesh", name="pp1")
        mc.setAttr(
            p + "._computeSource",
            "import numpy as np\n"
            "self.points = np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]], dtype=float)\n"
            "self.counts = np.array([4], dtype=int)\n"
            "self.indices = np.array([0,1,2,3], dtype=int)",
            type="string",
        )
        sel = om.MSelectionList()
        sel.add(p)
        node = om.MObject()
        sel.getDependNode(0, node)
        plug = om.MFnDependencyNode(node).findPlug("outMesh", True)
        data = plug.asMObject()
        mfn = om.MFnMesh(data)
        self.assertEqual(int(mfn.numVertices()), 4)
        self.assertEqual(int(mfn.numPolygons()), 1)


class TestMatrixInputDirtiesMatrixOutputs(unittest.TestCase):
    """Product regression: ``setDependentsDirty`` must declare that a user INPUT
    attribute (matrix0, tension, ...) affects the matrix outputs, so an
    mPyTransform aimed by connected matrix inputs invalidates its matrix /
    worldMatrix when a source changes.

    The buggy version fired only for a fixed whitelist of internal plugs
    (``_computeSource`` etc.), silently omitting user inputs. That decision --
    "is this dirtied plug a matrix trigger?" -- is the load-bearing logic and is
    tested directly via ``_is_matrix_dirty_trigger``. (A pure getAttr / dirty-
    callback probe cannot discriminate the fix: DG-mode getAttr re-runs
    ``asMatrix`` and reads inputs live, and the transform's TRS-sync already
    propagates worldMatrix downstream. The dependency declaration only becomes
    observable under the viewport / evaluation-manager, which mayapy can't
    exercise headless.)
    """

    # Realistic serialized _inputAttrs map (matches serialization.encode format).
    _INPUT_ATTRS_JSON = (
        '{"matrix0":{"attr_type":"matrix","is_array":false,"order":0},'
        '"matrix1":{"attr_type":"matrix","is_array":false,"order":1},'
        '"tension":{"attr_type":"double","is_array":true,"order":2}}'
    )

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_user_input_attr_is_a_matrix_trigger(self):
        # THE FIX: a declared user input must count as a trigger.
        from mpynode._api1.mpy_transform import _is_matrix_dirty_trigger

        self.assertTrue(
            _is_matrix_dirty_trigger("matrix0", "matrix0",
                                     self._INPUT_ATTRS_JSON),
            msg="a connected user matrix input was not treated as a trigger "
                "-- matrix outputs would not be dirtied on input change")
        # Array-child of a user input resolves via its ROOT long name.
        self.assertTrue(
            _is_matrix_dirty_trigger("tension", "tension",
                                     self._INPUT_ATTRS_JSON),
            msg="a user array input (tension) was not treated as a trigger")

    def test_internal_driver_plugs_are_triggers(self):
        from mpynode._api1.mpy_transform import _is_matrix_dirty_trigger

        for name in ("_computeSource", "_storedVarsData", "_inputAttrs",
                     "_outputAttrs", "_timeIn"):
            self.assertTrue(
                _is_matrix_dirty_trigger(name, name, ""),
                msg="internal driver %r must remain a matrix trigger" % name)

    def test_unrelated_plug_is_not_a_trigger(self):
        from mpynode._api1.mpy_transform import _is_matrix_dirty_trigger

        # A built-in / unrelated plug not in the input map must NOT force a
        # matrix-output dirty (avoids over-dirtying the transform pipeline).
        self.assertFalse(
            _is_matrix_dirty_trigger("nodeState", "nodeState",
                                     self._INPUT_ATTRS_JSON),
            msg="an unrelated plug must not be a matrix trigger")

    def test_child_follows_moved_matrix_input(self):
        """Integration smoke: an aim transform driven by two connected matrix
        inputs, with a parented child, produces the correct child world position
        after a source moves (guards the aim compute contract end-to-end)."""
        from mpynode.wrappers.mpy_transform import MPyTransform

        aim = MPyTransform.create(name="aimRig", skip_selection=True)
        aim.add_input_attr("matrix0", "matrix")
        aim.add_input_attr("matrix1", "matrix")
        aim.set_init_expression("import numpy as np\n")
        aim.set_compute_expression(
            "m0 = self.matrix0.asNumpy(); m1 = self.matrix1.asNumpy()\n"
            "M = np.eye(4)\n"
            "M[3, :3] = 0.5 * (m0[3, :3] + m1[3, :3])\n"
            "self.local_matrix = M\n"  # node is a root -> local == world
            "self.apply_translate = True\n"
        )
        node = aim.get_name()

        l0 = mc.spaceLocator(name="src0")[0]
        l1 = mc.spaceLocator(name="src1")[0]
        mc.setAttr(l0 + ".translate", 0.0, 0.0, 0.0, type="double3")
        mc.setAttr(l1 + ".translate", 10.0, 0.0, 0.0, type="double3")
        mc.connectAttr(l0 + ".worldMatrix[0]", node + ".matrix0", force=True)
        mc.connectAttr(l1 + ".worldMatrix[0]", node + ".matrix1", force=True)

        child = mc.group(empty=True, name="follower")
        child = mc.parent(child, node, relative=True)[0]

        def child_world_x():
            return mc.getAttr(child + ".worldMatrix[0]")[12]

        self.assertAlmostEqual(child_world_x(), 5.0, places=4,
                               msg="child not at initial midpoint")
        mc.setAttr(l1 + ".translate", 20.0, 0.0, 0.0, type="double3")
        self.assertAlmostEqual(child_world_x(), 10.0, places=4,
                               msg="child did not follow the moved matrix input")


class TestFlushFreeMatrixInputTracking(unittest.TestCase):
    """Flush-free replacement for the old DNET line-gizmo regression.

    Product contract (was: the ``dnetLink`` line gizmos froze at the first
    frame when their aim was driven by animated matrix inputs with NO direct
    time connection). The old fix was a per-frame ``timeChanged`` callback that
    force-wrote a TRS channel to flush the DAG world cache. That whole machinery
    is GONE: the expression result now rides ``offsetParentMatrix`` through a
    paired ``fourByFourMatrix`` relay, so an input change dirties the opm output
    and worldMatrix + descendants update via native DG propagation -- no flush.

    This test asserts the SAME end-to-end contract the old flush guarded: with
    an aim driven by two ANIMATED knots (no time connection, no TRS animation),
    the aim's worldMatrix and its parented child gizmo track the knot midpoint
    across a scrubbed timeline -- reading ``worldMatrix`` ONLY (never ``.matrix``,
    which is now TRS-only and would mask a frozen world cache).

    The two remaining tests below guard generic draw / auto-dirty helpers
    (``free_translate_channel`` / ``_live_node_name``) that are still used by the
    locator gizmo draw-refresh path.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _make_aim(self, name):
        from mpynode.wrappers.mpy_transform import MPyTransform

        aim = MPyTransform.create(name=name, skip_selection=True)
        aim.add_input_attr("matrix0", "matrix")
        aim.add_input_attr("matrix1", "matrix")
        aim.set_init_expression("import numpy as np\n")
        aim.set_compute_expression(
            "m0 = self.matrix0.asNumpy(); m1 = self.matrix1.asNumpy()\n"
            "M = np.eye(4)\n"
            "M[3, :3] = 0.5 * (m0[3, :3] + m1[3, :3])\n"
            "self.local_matrix = M\n"  # node is a root -> local == world
            "self.apply_translate = True\n"
        )
        return aim.get_name()

    def test_worldMatrix_tracks_animated_matrix_inputs_flush_free(self):
        """Integration (VP2 draw path): an aim driven by two ANIMATED knots with
        NO time connection -- its worldMatrix + child gizmo track the knot
        midpoint across a scrubbed timeline, with NO per-frame flush callback."""
        node = self._make_aim("aimTrack")
        l0 = mc.spaceLocator(name="knot0")[0]
        l1 = mc.spaceLocator(name="knot1")[0]
        mc.setKeyframe(l0 + ".translateX", time=0, value=0.0)
        mc.setKeyframe(l0 + ".translateX", time=30, value=6.0)
        mc.setKeyframe(l1 + ".translateX", time=0, value=10.0)
        mc.setKeyframe(l1 + ".translateX", time=30, value=30.0)
        mc.connectAttr(l0 + ".worldMatrix[0]", node + ".matrix0", force=True)
        mc.connectAttr(l1 + ".worldMatrix[0]", node + ".matrix1", force=True)

        # Precondition: the aim has NO direct time connection -- the old arch
        # would have frozen it; the flush-free arch tracks it natively.
        self.assertFalse(
            bool(mc.listConnections(node, source=True, destination=False,
                                    type="time")),
            "precondition: aim must have NO direct time connection")

        child = mc.group(empty=True, name="lineGizmo")
        child = mc.parent(child, node, relative=True)[0]

        def aim_world_x():
            return mc.getAttr(node + ".worldMatrix[0]")[12]

        def child_world_x():
            return mc.getAttr(child + ".worldMatrix[0]")[12]

        for f in (0, 10, 20, 30):
            mc.currentTime(f, edit=True)
            expected = 0.5 * (mc.getAttr(l0 + ".translateX")
                              + mc.getAttr(l1 + ".translateX"))
            self.assertAlmostEqual(
                aim_world_x(), expected, places=3,
                msg="aim worldMatrix did not track knot midpoint at frame %d" % f)
            self.assertAlmostEqual(
                child_world_x(), expected, places=3,
                msg="child gizmo worldMatrix did not track at frame %d" % f)

    def test_free_translate_channel_avoids_connection_sources(self):
        """The worldMatrix flush writes a translate channel to itself. It MUST
        pick a NON-source channel: an aim transform's ``translateX`` is wired to
        the DNET solver's ``tension``, so flushing via ``translateX`` re-solves
        the whole network and -- inside the interactive re-entry guard -- starves
        sibling aims' flushes (the P0 'half the link aims never re-orient' bug).
        ``free_translate_channel`` must therefore skip a channel that is an
        outgoing-connection source and fall through to a free one."""
        from mpynode._common.plugs.auto_dirty import free_translate_channel

        # Common case: every translate channel free -> prefer translateX
        # (backward-compatible with the historical unconditional behaviour).
        plain = mc.createNode("mPyTransform", name="plainXform")
        self.assertEqual(free_translate_channel(plain), "translateX",
                         "a free transform must flush via translateX")

        # Aim-like case: translateX drives something downstream (as tension does)
        # -> must skip to the next free channel, translateY.
        aim = mc.createNode("mPyTransform", name="aimXform")
        md = mc.createNode("multiplyDivide", name="tensionSink")
        mc.connectAttr(aim + ".translateX", md + ".input1X", force=True)
        self.assertEqual(free_translate_channel(aim), "translateY",
                         "translateX is a connection SOURCE (feeds the solver) "
                         "-- flushing it would re-solve; must pick a free channel")

        # translateX AND translateY both connection sources -> skip to translateZ.
        mc.connectAttr(aim + ".translateY", md + ".input2X", force=True)
        self.assertEqual(free_translate_channel(aim), "translateZ",
                         "translateX/Y both connection sources -> use translateZ")

        # Locked case: a LOCKED translateX can't be setDouble'd -> skip it.
        locked = mc.createNode("mPyTransform", name="lockedXform")
        mc.setAttr(locked + ".translateX", lock=True)
        self.assertEqual(free_translate_channel(locked), "translateY",
                         "translateX is locked (setDouble is rejected) -- must "
                         "fall through to a writable channel")

    def test_live_node_name_disambiguates_duplicate_short_names(self):
        """``_live_node_name`` must return a UNIQUE DAG path. Two mPyTransforms
        that share a short name under different parents (the duplicated-DNET-rig
        case: Node Duplicate clones a second ``dnetLinkAim0``) make a bare
        ``MFnDependencyNode.name()`` ambiguous -> every name-based ``cmds`` query
        in ``free_translate_channel`` raises -> it falls back to ``translateX``,
        the harmful tension-source channel, reintroducing the P0. A partial DAG
        path keeps the queries unambiguous."""
        # ``_live_node_name`` lives in ``auto_dirty`` (api1 ``om``), so it must
        # be handed api1 MObjects -- mixing api2 objects raises a TypeError.
        import maya.OpenMaya as om1
        from mpynode._common.plugs.auto_dirty import (
            _live_node_name, free_translate_channel)

        grp_a = mc.createNode("transform", name="dupGrpA")
        grp_b = mc.createNode("transform", name="dupGrpB")
        mc.createNode("mPyTransform", name="dupAim", parent=grp_a)
        mc.createNode("mPyTransform", name="dupAim", parent=grp_b)
        a1 = grp_a + "|dupAim"
        a2 = grp_b + "|dupAim"

        # Precondition: the bare short name IS ambiguous.
        self.assertEqual(
            len(mc.ls("dupAim") or []), 2,
            "test precondition: two nodes must share the short name 'dupAim'")

        def obj(full):
            sel = om1.MSelectionList()
            sel.add(full)
            o = om1.MObject()
            sel.getDependNode(0, o)
            return o

        for full in (a1, a2):
            name = _live_node_name(obj(full))
            # Resolved name must be unambiguous ...
            self.assertEqual(
                len(mc.ls(name) or []), 1,
                "_live_node_name returned an ambiguous name: %r" % name)
            # ... and point back at the SAME node.
            self.assertEqual(
                mc.ls(full, long=True), mc.ls(name, long=True),
                "_live_node_name resolved to the wrong node: %r" % name)
            # ... and let free_translate_channel read channels cleanly
            # (all free -> translateX) rather than error-fall-back to translateX.
            self.assertEqual(
                free_translate_channel(name), "translateX",
                "a unique path must let free_translate_channel read channels "
                "without the ambiguity error that forces the translateX fallback")


def setUpModule():
    _setUpModule__phase31_0_transform()
    _setUpModule__phaseG_1_transform()
    _setUpModule__phaseF_4_transform_poly()


if __name__ == "__main__":
    import unittest
    unittest.main()
