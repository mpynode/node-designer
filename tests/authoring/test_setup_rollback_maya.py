"""Test setup-body rollback + undo-after-rollback (§9 test 9).

Proves that when an authored self-first `setup(self)` body fails PART-WAY
through (after creating the render transform + shape, the node `self` already
exists -- build() owns it), it (a) rolls back its partial render nodes leaving
NO orphans, (b) `build()` swallows the setup error so the node is BUILT but
UNWIRED (NOT degraded to a different bare node), and (c) a single `mc.undo()`
afterward does NOT crash and FULLY restores the scene. This must hold on BOTH
Maya 2024 AND Maya 2026 (the undo-replay / no-op-chunk behavior is
version-sensitive).
"""

import unittest

from maya import cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init
from mpynode._base.commands import build_new_or_setup_command, run_undoable


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestSetupRollbackMaya(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_mpymesh_rollback_on_partial_failure_and_undo_works(self):
        """Force mPyMesh setup to fail AFTER creating transform+shape, verify
        the body rolls back its render orphans, build() leaves the node
        built-but-unwired, and a single undo fully restores the scene."""

        # Capture scene state before.
        before = set(mc.ls(long=True))

        # Injection: patch mc.sets to raise when called by the setup body.
        # The mPyMesh setup (against the pre-built self) creates: transform,
        # shape, connectAttr, then mc.sets. We want mc.sets to fail so the
        # body's render-node rollback runs and the error propagates to build().
        original_sets   = mc.sets
        sets_call_count = [0]

        def patched_sets(*args, **kwargs):
            sets_call_count[0] += 1
            # The body calls mc.sets(shape, edit=True, forceElement="initialShadingGroup")
            # Raise on this call to simulate mid-setup failure.
            if kwargs.get('forceElement') == 'initialShadingGroup':
                raise RuntimeError("Injected failure in mc.sets")
            return original_sets(*args, **kwargs)

        try:
            mc.sets = patched_sets

            # Run the command via run_undoable (wraps in one undo chunk).
            cmd = build_new_or_setup_command("mPyMesh", mode=None, auto_setup=True)
            run_undoable(cmd)

            # build-then-wire: build() succeeds (mPyMesh exists), the render-shape
            # wiring fails at the injected point -> body rolls back its render
            # nodes, build() swallows the error -> node built but unwired.
            # 1. NO orphan render nodes (body rollback cleaned transform+shape).
            orphan_render_nodes = [n for n in mc.ls()
                                   if n.endswith("Render") or n.endswith("RenderShape")]
            self.assertEqual(orphan_render_nodes, [],
                            "Body rollback must delete transform+shape orphans")

            # 2. The mPyMesh node exists (build() owns it; setup failure does
            #    NOT delete it).
            self.assertIsNotNone(cmd.created_name,
                                "build() must leave the node built")
            self.assertTrue(mc.objExists(cmd.created_name))
            self.assertEqual(mc.nodeType(cmd.created_name), "mPyMesh")

            # 3. The node has NO *Render/*RenderShape child (built-but-unwired).
            render_xform = cmd.created_name + "Render"
            render_shape = cmd.created_name + "RenderShape"
            self.assertFalse(mc.objExists(render_xform),
                            "Built-but-unwired node must not have render transform")
            self.assertFalse(mc.objExists(render_shape),
                            "Built-but-unwired node must not have render shape")

            # 4. Verify the injection actually fired (rollback path was exercised).
            self.assertGreater(sets_call_count[0], 0,
                              "mc.sets must have been called to verify injection")

            # 5. mc.undo() does not raise.
            try:
                mc.undo()
            except Exception as exc:
                self.fail("mc.undo() must not crash after rollback: %s" % exc)

            # 6. Scene FULLY restored (node + any seed gone).
            after = set(mc.ls(long=True))
            self.assertEqual(after, before,
                            "One undo must fully restore scene to before state")

        finally:
            # Restore mc.sets.
            mc.sets = original_sets


if __name__ == "__main__":
    unittest.main()
