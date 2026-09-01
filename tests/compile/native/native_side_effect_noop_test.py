"""A blessed ``NativeSideEffect`` method call is a compiled NO-OP.

``update_weights`` (and, for twist/swing, ``sync_paint``) are registered with a
``NativeSideEffect`` lower marker: they perform an interactive-only plug side
effect (write the ``weightList`` paint scratchpad) with NO numeric kernel, so a
BARE ``self.<method>(...)`` expression statement must lower to nothing rather than
honest-reject the whole deform. The deform math around it (blessed ``Transpile``
methods reading the inherited skin plugs) still lowers to pure C++.

HARD RULE preserved: this only drops a bare STATEMENT-context call (no value); a
NativeSideEffect method used in value position, or any other unsupported bare
expression, still fails.
"""
import unittest

from mpynode.native.compiler import nd_lower
from mpynode.native.compiler.errors import UnsupportedSpec
from mpynode.native.compiler.node_scaffold import _reject_unbound_deform_reads


_DEFORM_WITH_SIDE_EFFECT = (
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "self.update_weights(self.weightList)\n"          # NativeSideEffect -> no-op
    "deformed = self.linear_blend(rest, self.weightList, self.matrix, "
    "self.bindPreMatrix)\n"
    "mesh.setPoints(rest + float(self.envelope) * (deformed - rest))\n"
)


class TestNativeSideEffectNoOp(unittest.TestCase):
    def test_bare_side_effect_call_lowers_to_nothing(self):
        spec = {"mpy_type": "mPySkinCluster", "init": "import numpy as np\n",
                "compute": _DEFORM_WITH_SIDE_EFFECT}
        body = nd_lower.lower_deform([], spec, "MPxSkinCluster")
        self.assertTrue(body, "deform with a bare NativeSideEffect call "
                              "should lower, not raise")
        joined = "\n".join(body)
        # the side-effecting call must NOT appear in the emitted C++.
        self.assertNotIn("update_weights", joined,
                         "NativeSideEffect call leaked into the C++")
        # the surrounding deform math still lowers (LBS helper emitted).
        self.assertIn("_h_linear_blend", joined)

    def test_unknown_bare_call_still_rejects(self):
        # A bare call to a method that is NOT a registered NativeSideEffect must
        # still honest-reject (no silent drop of arbitrary side effects).
        spec = {"mpy_type": "mPySkinCluster",
                "compute": ("mesh = self.outputGeometry[0]\n"
                            "rest = mesh.getPoints()\n"
                            "self.not_a_blessed_method(rest)\n"
                            "mesh.setPoints(rest)\n")}
        with self.assertRaises(UnsupportedSpec):
            nd_lower.lower_deform([], spec, "MPxSkinCluster")


class TestDeformGuardBlessedMethods(unittest.TestCase):
    """The AI-port honest-reject guard must never blame a blessed METHOD name
    (it tokenizes as a ``self.<name>`` ref but is a registered API method)."""

    def test_guard_ignores_blessed_method_calls(self):
        # only self-refs are blessed methods + inherited skin plugs -> no orphan.
        spec = {"mpy_type": "mPySkinCluster",
                "compute": ("mesh = self.outputGeometry[0]\n"
                            "rest = mesh.getPoints()\n"
                            "self.update_weights(self.weightList)\n"
                            "d = self.linear_blend(rest, self.weightList, "
                            "self.matrix, self.bindPreMatrix)\n"
                            "mesh.setPoints(d)\n")}
        # must NOT raise (nothing genuinely unbound).
        _reject_unbound_deform_reads([], spec, "MPxSkinCluster")

    def test_guard_still_names_genuine_orphan(self):
        # a real unbound read alongside a blessed call -> reject, name the orphan
        # (``mysteryScale``), NEVER the method.
        spec = {"mpy_type": "mPySkinCluster",
                "compute": ("mesh = self.outputGeometry[0]\n"
                            "rest = mesh.getPoints()\n"
                            "d = self.linear_blend(rest, self.weightList, "
                            "self.matrix, self.bindPreMatrix)\n"
                            "mesh.setPoints(d * self.mysteryScale)\n")}
        with self.assertRaises(UnsupportedSpec) as cm:
            _reject_unbound_deform_reads([], spec, "MPxSkinCluster")
        msg = str(cm.exception)
        self.assertIn("mysteryScale", msg)
        self.assertNotIn("linear_blend", msg)


if __name__ == "__main__":
    unittest.main()
