"""mPyTransform gated local-matrix contract.

MPyTransform mirrors mPyIkSolver (single joint): the expression writes
``self.local_matrix`` (default ``None``) + ``self.apply_rotate`` /
``apply_translate`` / ``apply_scale`` gates (default ``True``). It is,
conceptually, a single-"joint" IK solver with the bind offset pinned to identity,
so a gate set ``False`` falls back to the transform's own live TRS and a vanilla
node (``local_matrix`` ``None``) behaves exactly like a normal Maya transform.

Dispatch: ``local_matrix`` (if set AND >=1 gate open) > no-op. ``local_matrix``
None (checked first) OR all gates False => ``offsetParentMatrix`` identity.

There is NO ``world_matrix`` slot -- the node never reads its own DAG parent.
WORLD placement is opt-in and cycle-free: read the parent world from a CONNECTED
matrix input and set ``self.local_matrix = worldDesired @ inv(parentWorld)``.
"""

from __future__ import annotations

import unittest

import maya.cmds as mc
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


_ROT90Z = (
    "import numpy as np\n"
    "m = np.eye(4)\n"
    "m[0, 0] = 0.0; m[0, 1] = 1.0\n"   # row-vector rotate 90 about Z
    "m[1, 0] = -1.0; m[1, 1] = 0.0\n"
)


class TestGatedTransformContract(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    # -- inertness -----------------------------------------------------------

    def test_default_is_inert_plain_transform(self):
        """No expression -> every slot at its default -> opm identity -> the node
        is a plain Maya transform (live SRT shows through world + local)."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".translateY", 5.0)
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[13], 5.0)
        self.assertAlmostEqual(mc.getAttr(n + ".matrix")[13], 5.0)

    def test_gates_false_ignores_matrix(self):
        """A matrix set but all gates explicitly False -> the matrix is ignored;
        the node stays a plain transform driven by its live channels. (Gates
        default True now, so this must close them explicitly.)"""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".translateY", 5.0)
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[3, 1] = 100.0\n"
            "self.local_matrix = m\n"
            "self.apply_rotate = False\n"
            "self.apply_translate = False\n"
            "self.apply_scale = False\n",
            type="string",
        )
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[13], 5.0)

    def test_default_gates_matrix_drives_all_channels(self):
        """Gates default True: setting a matrix with NO explicit gates drives all
        channels (translate here) without opening gates by hand."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".translateY", 5.0)
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[3, 1] = 100.0\n"
            "self.local_matrix = m\n",  # no apply_* -> default True
            type="string",
        )
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[13], 100.0)

    def test_no_matrix_inert_despite_default_true_gates(self):
        """Gates default True but both matrices None -> still a no-op (the
        dispatch checks "no matrix set" first), so a vanilla node with a
        matrix-free expression stays a plain transform."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".translateY", 5.0)
        mc.setAttr(
            n + "._computeSource",
            "x = 1 + 1\n",  # touches nothing; matrices stay None
            type="string",
        )
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[13], 5.0)

    # -- local drive ---------------------------------------------------------

    def test_local_matrix_all_gates_drives_world_at_root(self):
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[3, 0] = 7.0; m[3, 1] = 8.0; m[3, 2] = 9.0\n"
            "self.local_matrix = m\n"
            "self.apply_rotate = True\n"
            "self.apply_translate = True\n"
            "self.apply_scale = True\n",
            type="string",
        )
        wm = mc.getAttr(n + ".worldMatrix[0]")
        self.assertAlmostEqual(wm[12], 7.0)
        self.assertAlmostEqual(wm[13], 8.0)
        self.assertAlmostEqual(wm[14], 9.0)

    def test_apply_translate_only_replaces_translate(self):
        """apply_translate alone: translation comes wholly from the matrix; the
        live translateX is overridden (gate replaces the channel). Gates default
        True, so rotate/scale are closed explicitly to isolate translate."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".translateX", 3.0)
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[3, 1] = 10.0\n"
            "self.local_matrix = m\n"
            "self.apply_translate = True\n"
            "self.apply_rotate = False\n"
            "self.apply_scale = False\n",
            type="string",
        )
        wm = mc.getAttr(n + ".worldMatrix[0]")
        self.assertAlmostEqual(wm[12], 0.0)
        self.assertAlmostEqual(wm[13], 10.0)

    def test_apply_rotate_only_keeps_live_translate(self):
        """apply_rotate alone: rotation from the matrix, translate/scale stay
        live (un-gated channels fall back to the transform's own TRS). Gates
        default True, so translate/scale are closed explicitly here."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".translateX", 3.0)
        mc.setAttr(
            n + "._computeSource",
            _ROT90Z + "self.local_matrix = m\n"
            "self.apply_rotate = True\n"
            "self.apply_translate = False\n"
            "self.apply_scale = False\n",
            type="string",
        )
        wm = mc.getAttr(n + ".worldMatrix[0]")
        # translate preserved from the live channel
        self.assertAlmostEqual(wm[12], 3.0)
        self.assertAlmostEqual(wm[13], 0.0)
        # rotation taken from the matrix (row0 == (0, 1, 0))
        self.assertAlmostEqual(wm[0], 0.0)
        self.assertAlmostEqual(wm[1], 1.0)

    # -- world placement via a CONNECTED parent input ------------------------

    def test_world_placement_via_connected_parent_is_dg_tracked(self):
        """``world_matrix`` is gone; WORLD placement is opt-in via a CONNECTED
        parent matrix input. The child lands at the absolute target regardless of
        the parent, AND re-solves when the parent moves -- the old imperative
        DAG-parent read left this stale (the reason the slot was axed)."""
        from mpynode.wrappers.mpy_transform import MPyTransform

        parent = mc.group(empty=True, name="parentGrp")
        mc.setAttr(parent + ".translateY", 7.0)
        n = mc.createNode("mPyTransform", name="t1", parent=parent)
        MPyTransform(n).add_input_attr("parentWorld", "matrix")
        mc.connectAttr(parent + ".worldMatrix[0]", n + ".parentWorld",
                       force=True)
        mc.setAttr(
            n + "._computeSource",
            "import numpy as np\n"
            "P = self.parentWorld.asNumpy()\n"
            "wm = np.eye(4)\n"
            "wm[3, 0] = 1.0; wm[3, 1] = 2.0; wm[3, 2] = 3.0\n"
            "self.local_matrix = wm @ np.linalg.inv(P)\n"
            "self.apply_rotate = True\n"
            "self.apply_translate = True\n"
            "self.apply_scale = True\n",
            type="string",
        )
        wm = mc.getAttr(n + ".worldMatrix[0]")
        # Absolute world regardless of the parent's translateY == 7.
        self.assertAlmostEqual(wm[12], 1.0)
        self.assertAlmostEqual(wm[13], 2.0)
        self.assertAlmostEqual(wm[14], 3.0)

        # Move the parent -> the child RE-SOLVES to the same absolute world
        # (DG-tracked fan-in, no stale offsetParentMatrix).
        mc.setAttr(parent + ".translateY", -4.0)
        mc.setAttr(parent + ".translateX", 11.0)
        wm2 = mc.getAttr(n + ".worldMatrix[0]")
        self.assertAlmostEqual(wm2[12], 1.0)
        self.assertAlmostEqual(wm2[13], 2.0)
        self.assertAlmostEqual(wm2[14], 3.0)

    # -- robustness ----------------------------------------------------------

    def test_malformed_matrix_is_noop(self):
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".translateY", 5.0)
        mc.setAttr(
            n + "._computeSource",
            "self.local_matrix = 'not a matrix'\n"
            "self.apply_translate = True\n",
            type="string",
        )
        # Uncoercible matrix -> treated as None -> no-op -> plain transform.
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[13], 5.0)


class TestGatedTransformInterface(unittest.TestCase):
    def test_internal_api_slots_are_the_four_writes_only(self):
        """The Internals pane holds ONLY the four gated write slots (world_matrix
        was axed); the SRT + shear + rotateOrder channels are INPUT attributes,
        not internal vars."""
        from mpynode.wrappers.mpy_transform import MPyTransform

        slots      = MPyTransform.INTERNAL_API_SLOTS
        directions = {s[0]: s[1] for s in slots}
        self.assertEqual(
            set(directions),
            {"local_matrix",
             "apply_rotate", "apply_translate", "apply_scale"},
        )
        for name in directions:
            self.assertEqual(directions[name], "write")
        # world_matrix was removed; the channels must NOT be internal slots.
        for name in ("world_matrix", "translate", "rotate", "scale", "shear",
                     "rotate_order"):
            self.assertNotIn(name, directions)

    def test_channels_exposed_as_input_plugs(self):
        """translate / rotate / scale / shear / rotateOrder (+ children) are
        promoted to always-visible INPUT attributes via EXPOSED_INPUT_PLUGS."""
        from mpynode.wrappers.mpy_transform import MPyTransform

        exposed = set(MPyTransform.EXPOSED_INPUT_PLUGS)
        for name in ("translate", "rotate", "scale", "shear", "rotateOrder"):
            self.assertIn(name, exposed)
        # X/Y/Z children listed so they expand under the parent compound.
        for child in ("translateX", "rotateZ", "scaleY", "shearXY"):
            self.assertIn(child, exposed)

    def test_legacy_internals_removed(self):
        from mpynode.wrappers.mpy_transform import MPyTransform

        names = [s[0] for s in MPyTransform.INTERNAL_API_SLOTS]
        # ``rotate_order`` is back as a legit per-channel READ; ``time`` /
        # ``parent_matrix`` / the ``output_matrix`` write slot stay removed, and
        # ``world_matrix`` was axed (WORLD is now a connected-parent expression).
        for gone in ("time", "parent_matrix", "output_matrix", "world_matrix"):
            self.assertNotIn(gone, names)


if __name__ == "__main__":
    unittest.main()
