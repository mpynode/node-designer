"""Deterministic mPyFile preset-interface fallback (regression for the mega drop).

ROOT CAUSE (2026-07-19 mega): the transient ``createNode("mPyFile")`` preset
capture is best-effort (``except: return {}``). When it flakily returned empty in
a batch build, the texture node silently lost its uvCoord/fileName interface, the
porter rejected "reads undeclared self attr(s) uvCoord", and the node was DROPPED
(fileTexture/scanlineTex/basicTexture) -- while gameOfLifeTex in the SAME run
captured fine. A pinned static fallback makes the interface deterministic so a
flaky live capture can never again strip it.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from ._setup import standalone_init, ensure_plugins_loaded


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_SCANLINE_COMPUTE = (
    "arr = _grid(self.fileName)\n"
    "u, v = self.uvCoord\n"
    "self.outColor = (u, v, 0.0)\n"
    "self.outAlpha = 1.0\n"
)


class TestPresetCaptureDeterministic(unittest.TestCase):
    """capture_preset_attrs_transient reads the declarative SSOT: it fills every
    REFERENCED mPyFile preset with no live Maya node and no createNode."""

    def test_captures_referenced_presets(self):
        from mpynode.native.spec import spec_extractor as se
        pin, pout = se.capture_preset_attrs_transient(
            "mPyFile", _SCANLINE_COMPUTE, "", {}, {})
        self.assertIn("uvCoord", pin)
        self.assertIn("fileName", pin)
        self.assertIn("outColor", pout)
        self.assertIn("outAlpha", pout)
        # uvCoord is a float2 input; outColor a color output.
        self.assertEqual(pin["uvCoord"]["attr_type"], "float2")
        self.assertEqual(pout["outColor"]["attr_type"], "color")

    def test_does_not_add_unreferenced_presets(self):
        from mpynode.native.spec import spec_extractor as se
        pin, pout = se.capture_preset_attrs_transient(
            "mPyFile", "u, v = self.uvCoord\nself.outColor = (u, v, 0)\n",
            "", {}, {})
        # colorSpace is a real preset but not referenced -> not injected.
        self.assertNotIn("colorSpace", pin)

    def test_user_attrs_win(self):
        from mpynode.native.spec import spec_extractor as se
        # If the user declared uvCoord themselves, capture must not clobber it.
        pin, pout = se.capture_preset_attrs_transient(
            "mPyFile", _SCANLINE_COMPUTE, "", {"uvCoord": {"x": 1}}, {})
        self.assertNotIn("uvCoord", pin)

    def test_gated_to_mpyfile(self):
        from mpynode.native.spec import spec_extractor as se
        pin, pout = se.capture_preset_attrs_transient(
            "mPyMesh", _SCANLINE_COMPUTE, "", {}, {})
        self.assertEqual((pin, pout), ({}, {}))


class TestTransientCaptureResilient(unittest.TestCase):
    """The porter no longer touches createNode: capture yields the full interface
    EVEN when maya.cmds.createNode is monkeypatched to raise (the exact 2026-07-19
    mega failure mode is now structurally impossible)."""

    def test_survives_createNode_failure(self):
        import maya.cmds as mc
        from mpynode.native.spec import spec_extractor as se

        orig = mc.createNode

        def _boom(*a, **k):
            raise RuntimeError("simulated flaky createNode failure")

        mc.createNode = _boom
        try:
            pin, pout = se.capture_preset_attrs_transient(
                "mPyFile", _SCANLINE_COMPUTE, "", {}, {})
        finally:
            mc.createNode = orig
        self.assertIn("uvCoord", pin)
        self.assertIn("fileName", pin)
        self.assertIn("outColor", pout)


class TestStaticTablePinnedToLive(unittest.TestCase):
    """Drift guard: the static fallback table must match what the LIVE mPyFile
    node reports, so the fallback is byte-identical to the transient path."""

    def test_static_matches_live(self):
        import maya.cmds as mc
        from mpynode.native.spec import spec_extractor as se

        node = mc.createNode("mPyFile")
        try:
            for nm, static in se._MPYFILE_PRESET_META.items():
                if mc.attributeQuery(nm, node=node, exists=True) is not True:
                    self.fail("static table lists non-existent preset %r" % nm)
                live = se._preset_attr_meta(node, nm, mc)
                self.assertIsNotNone(live, "no live meta for %r" % nm)
                self.assertEqual(
                    static, live,
                    "static table drifted from live for %r:\n static=%r\n live=%r"
                    % (nm, static, live))
        finally:
            mc.delete(node)

    def test_every_referenced_preset_is_in_table(self):
        """Bidirectional drift guard (adversarial review finding #4): the table
        must also be COMPLETE. Any preset a texture template references (via
        self.<name> OR the getattr fileName) that exists on a live mPyFile but is
        ABSENT from the static table would be silently stripped again under a
        flaky capture -- with no loud porter reject to catch it. Fail loudly here
        so a new template forces a table update instead."""
        import os as _os
        import maya.cmds as mc
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import spec_extractor as se

        root = _os.environ.get("MPYNODE_ROOT") or _os.getcwd()
        tex = ["File Simple", "File Scanline", "File Composite",
               "Game Of Life Texture"]
        node = mc.createNode("mPyFile")
        try:
            for t in tex:
                mpn = _os.path.join(root, "templates", "MPyFile", t,
                                    "template.mpn")
                if not _os.path.isfile(mpn):
                    continue
                payload = mpn_io.load_mpn(mpn, trusted=True)
                compute = payload.get("compute") or payload.get("compute_source") or ""
                init = payload.get("init") or payload.get("init_source") or ""
                # self.<name> refs + fileName (reached inside read_texture()).
                refs = set(se._self_attr_refs("%s\n%s" % (compute, init)))
                refs.add("fileName")
                for nm in sorted(refs):
                    if nm.startswith("_"):
                        continue
                    if mc.attributeQuery(nm, node=node, exists=True) is not True:
                        continue  # not a DG preset (scratch var / injected slot)
                    meta = se._preset_attr_meta(node, nm, mc)
                    if meta is None:
                        continue  # no native C++ representation -> not backfillable
                    self.assertIn(
                        nm, se._MPYFILE_PRESET_META,
                        "%s references live preset %r absent from "
                        "_MPYFILE_PRESET_META -> would be silently stripped under "
                        "a flaky capture; add it to the static table" % (t, nm))
        finally:
            mc.delete(node)


class TestMpnAdapterCapturesInterface(unittest.TestCase):
    """End-to-end: adapting each texture template yields a spec WITH the texture
    interface (uvCoord present), so the porter never rejects it."""

    def test_texture_templates_have_uvcoord(self):
        import os as _os
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter as A

        root = _os.environ.get("MPYNODE_ROOT") or _os.getcwd()
        tex = ["File Simple", "File Scanline", "File Composite",
               "Game Of Life Texture"]
        for t in tex:
            mpn = _os.path.join(root, "templates", "MPyFile", t,
                                "template.mpn")
            if not _os.path.isfile(mpn):
                self.skipTest("template missing: %s" % mpn)
            spec = A.spec_from_mpn_payload(mpn_io.load_mpn(mpn, trusted=True))
            self.assertIn("uvCoord", spec.get("inputs") or {},
                          "%s adapted spec is missing uvCoord" % t)


class TestFileNameResilientToFlakyCreateNode(unittest.TestCase):
    """THE gap the fix must close (adversarial review, 2026-07-19): file_simple
    (fileTexture) and file_scanline (scanlineTex) never name ``self.fileName``
    in their own source -- they used to reach it via ``getattr(slf, "fileName")``
    in an Init helper, and now reach it inside the framework's read_texture() --
    so the self.<name> preset scan (and _fill_preset_fallback) can't see it.
    The indirection moved; the gap it opens is identical.
    fileName is captured ONLY by the reads_image_file special-case
    (capture_named_presets_transient), which was best-effort with NO static
    backfill. So under the SAME flaky ``createNode`` that caused the original mega
    drop, fileName was still stripped -> reads_image_file glue (_imgPixels/_imgOK)
    got no path input -> the AI port referenced undeclared symbols -> the node
    dropped/no-op'd AGAIN. And because uvCoord is now deterministic, this no longer
    trips the porter's LOUD rejection -- it silently links a no-op. The full fix
    must make fileName as deterministic as uvCoord."""

    _FILE_GETATTR = ["File Simple", "File Scanline"]

    def _adapt_with_flaky_createNode(self, template):
        import os as _os
        import maya.cmds as mc
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter as A

        root = _os.environ.get("MPYNODE_ROOT") or _os.getcwd()
        mpn = _os.path.join(root, "templates", "MPyFile", template,
                            "template.mpn")
        if not _os.path.isfile(mpn):
            self.skipTest("template missing: %s" % mpn)
        payload = mpn_io.load_mpn(mpn, trusted=True)
        orig = mc.createNode

        def _boom(*a, **k):
            raise RuntimeError("simulated flaky createNode (2026-07-19 mega)")

        mc.createNode = _boom
        try:
            return A.spec_from_mpn_payload(payload)
        finally:
            mc.createNode = orig

    def test_filename_survives_flaky_createNode(self):
        for t in self._FILE_GETATTR:
            spec = self._adapt_with_flaky_createNode(t)
            ins = spec.get("inputs") or {}
            # uvCoord is protected by the self.<name> fallback (already fixed).
            self.assertIn("uvCoord", ins,
                          "%s lost uvCoord under flaky createNode" % t)
            # fileName is the GAP: reached via getattr, captured only by the
            # best-effort named-preset path -> must be statically backfilled.
            self.assertIn("fileName", ins,
                          "%s lost fileName under flaky createNode (getattr path "
                          "has no static fallback)" % t)
            # capture_named_presets returns NORMALIZED entries (key "type"),
            # unlike the raw-meta preset path (key "attr_type").
            self.assertEqual(ins["fileName"]["type"], "string")


if __name__ == "__main__":
    unittest.main()
