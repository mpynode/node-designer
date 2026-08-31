"""Honest-reject guard on the deformer AI-port path.

Mirrors the plain-MPxNode ``emit_compute._unbound_self_reads`` guard: a deformer
whose deform() did NOT deterministically lower would be AI-ported, and if it READS
a ``self.<attr>`` that is neither a declared input, an inherited deformer/skin plug
the port binds, nor assigned in compute/init, the compiled node cannot obtain that
value -- so it must be rejected (build "dropped"), never shipped as a silent no-op.
"""

from __future__ import annotations

import unittest

from mpynode.native.compiler.node_scaffold import _reject_unbound_deform_reads
from mpynode.native.compiler.errors import UnsupportedSpec
from mpynode._defaults import skin_cluster_defaults as scd


def _ins(*plugs):
    return [{"plug": p, "member": "a" + p, "kind": "inputs",
             "meta": {"type": "double", "is_array": False}} for p in plugs]


class TestDeformHonestReject(unittest.TestCase):
    def test_rejects_undeclared_external_read(self):
        # A skin compute reading an external stored var (never declared, never
        # written) must reject -- the AI port cannot reconstruct it. (The spec
        # carries mpy_type as the production codegen always does.)
        spec = {"mpy_type": "mPySkinCluster",
                "compute": "mesh = self.outputGeometry[0]\n"
                           "w = self.clusterState\n"          # <- orphan
                           "mesh.setPoints(mesh.getPoints())\n"}
        with self.assertRaises(UnsupportedSpec):
            _reject_unbound_deform_reads([], spec, "MPxSkinCluster")

    def test_allows_inherited_skin_plugs(self):
        # Reads only inherited skin/deformer plugs + the blessed skinning method
        # -> bound by construction; no reject (this is what the shipped default
        # reads). The blessed method name (self.linear_blend) is allowed because
        # the guard unions methods_for_type(spec['mpy_type']) into the bound set.
        spec = {"mpy_type": "mPySkinCluster",
                "compute": scd.DEFAULT_COMPUTE_SOURCE,
                "init": scd.DEFAULT_INIT_SOURCE}
        _reject_unbound_deform_reads([], spec, "MPxSkinCluster")  # no raise

    def test_allows_declared_user_input(self):
        spec = {"compute": "mesh = self.outputGeometry[0]\n"
                           "mesh.setPoints(mesh.getPoints() + self.offsets)\n"}
        _reject_unbound_deform_reads(_ins("offsets"), spec,
                                     "MPxDeformerNode")  # no raise

    def test_allows_written_state(self):
        # A self attr WRITTEN in compute is a modelled persistent-state local, not
        # an unbound external read.
        spec = {"compute": "mesh = self.outputGeometry[0]\n"
                           "self.prev = mesh.getPoints()\n"
                           "mesh.setPoints(self.prev * 2.0)\n"}
        _reject_unbound_deform_reads([], spec, "MPxDeformerNode")  # no raise

    def test_skin_only_plugs_rejected_on_plain_deformer(self):
        # matrix/weightList are skin-only; a plain MPxDeformerNode has no such
        # inherited binding, so reading them there is an orphan.
        spec = {"compute": "mesh = self.outputGeometry[0]\n"
                           "w = self.weightList\n"
                           "mesh.setPoints(mesh.getPoints())\n"}
        with self.assertRaises(UnsupportedSpec):
            _reject_unbound_deform_reads([], spec, "MPxDeformerNode")


if __name__ == "__main__":
    unittest.main()
