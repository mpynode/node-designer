"""The assistant must know how EVERY node type publishes its result.

The prompt taught mPyLocator drawing, mPyTransform matrices and mPyFile's OSL,
and nothing about the other nine types beyond naming them under "PICKING A
TYPE". Asked for a convex-hull node, the assistant guessed the shape of the
answer and wrote::

    self.outMesh = (points, counts, indices)

which is not an error -- an output plug takes a finished Maya data MObject, a
tuple is not one, and nothing else was written -- so the node computed a correct
12-triangle hull and shipped an EMPTY mesh. Silently. A deformer that assigns
``self.points``, or an IK solver that assigns ``self.matrix``, fails the same
quiet way.

So: every type in the registry must appear in the write-contracts block (the
coverage gate -- a new node type cannot ship untaught), and every slot the block
teaches must be one the code really reads.
"""
from __future__ import annotations

import io
import os
import re
import unittest

from tests import _paths


def _prompts():
    from mpynode.ui.llm.system_prompt import (build_payload_system_prompt,
                                              build_system_prompt)

    return {"tool": build_system_prompt(), "payload": build_payload_system_prompt()}


def _source(rel):
    return io.open(os.path.join(_paths.ROOT, "scripts", "mpynode", *rel.split("/")),
                   encoding="utf-8").read()


class TestEveryNodeTypeIsTaught(unittest.TestCase):
    """The coverage gate."""

    def test_the_block_names_every_registered_type(self):
        from mpynode._node_registry import REGISTRY
        from mpynode.ui.llm import system_prompt

        block   = system_prompt._WRITE_CONTRACTS
        missing = sorted(t for t in REGISTRY if t not in block)
        self.assertEqual(
            missing, [],
            "no write contract for %s -- the assistant would have to guess how "
            "it publishes its result, which is how outMesh got a tuple"
            % (missing,))

    def test_both_prompts_carry_the_block(self):
        # Tool mode (API providers) and payload mode (the CLIs) are separate
        # prompts; the node that started this was written through one of them.
        from mpynode.ui.llm import system_prompt

        block = system_prompt._WRITE_CONTRACTS.strip()
        for name, prompt in _prompts().items():
            self.assertIn(block, prompt, name)
            self.assertNotIn("{WRITE_CONTRACTS}", prompt, name)

    def test_the_silent_failure_is_spelled_out(self):
        for name, prompt in _prompts().items():
            self.assertIn("SILENT", prompt, name)
            self.assertIn("EMPTY mesh", prompt, name)


class TestTaughtSlotsExist(unittest.TestCase):
    """What the block teaches has to match what the code reads."""

    #: bridge -> slots it must harvest as locals_out.get("<slot>")
    HARVESTED = {
        "_api2/mpy_mesh.py":          ("points", "counts", "indices", "colors",
                                       "outMesh"),
        "_api2/mpy_nurbs_curve.py":   ("cvs", "knots", "degree", "form",
                                       "outCurve"),
        "_api2/mpy_nurbs_surface.py": ("cvs", "degree_u", "degree_v", "form_u",
                                       "form_v", "num_cvs_u", "num_cvs_v",
                                       "outSurface"),
    }

    def test_geometry_slots_are_harvested(self):
        for rel, slots in self.HARVESTED.items():
            src = _source(rel)
            for slot in slots:
                self.assertIn('locals_out.get("%s"' % slot, src,
                              "%s does not read %r" % (rel, slot))

    def test_a_curve_really_does_not_harvest_points(self):
        # The negative the block states outright. If it ever becomes false the
        # warning should go, not linger and mislead.
        self.assertNotIn('locals_out.get("points"',
                         _source("_api2/mpy_nurbs_curve.py"))

    def test_the_deformer_family_really_deforms_through_the_handle(self):
        # The block teaches outputGeometry[0].getPoints()/setPoints() instead of
        # a points slot, because the points slot was removed.
        handles = _source("_common/plugs/mfn_handles.py")
        self.assertIn("def getPoints", handles)
        self.assertIn("def setPoints", handles)

    def test_the_ik_matrix_slots_are_real(self):
        ik = _source("_api1/mpy_iksolver.py")
        for slot in ("local_matrices", "world_matrices", "apply_rotate"):
            self.assertIn(slot, ik, slot)

    def test_the_constraint_presets_are_real(self):
        con = _source("_api2/mpy_constraint.py")
        for preset in ("targetTranslate", "targetRotate", "targetWeight",
                       "restTranslate", "restRotate"):
            self.assertIn(preset, con, preset)

    def test_the_block_teaches_no_invented_slot(self):
        from mpynode.ui.llm import system_prompt

        real = set()
        for slots in self.HARVESTED.values():
            real.update(slots)
        real.update({
            # deformer family + solver + constraint surfaces, checked above
            "outputGeometry", "envelope", "input", "matrix", "targetGeometry",
            "local_matrices", "world_matrices", "apply_rotate",
            "apply_translate", "apply_scale", "local_matrix",
            "targetTranslate", "targetRotate", "targetWeight", "outTranslate",
            "draw",
        })
        named = set(re.findall(r"self\.(\w+)\s*=", system_prompt._WRITE_CONTRACTS))
        self.assertTrue(named, "the block assigns nothing at all")
        self.assertEqual(sorted(named - real), [],
                         "the block teaches writes nothing reads")


if __name__ == "__main__":
    unittest.main()
