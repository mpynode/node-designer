"""Task 4.4: blessed-method preset capture in the native spec extractor.

A custom mPyFile compute that calls ``self.read_texture()`` /
``self.sample_texture(buf, u, v)`` reads the file-texture PRESET inputs
(colorSpace / wrapModeU / borderColor / ...) INSIDE the blessed adapters --
never textually as ``self.<preset>`` in the compute. The self.<name> preset
scan therefore misses them, so the compiled node would lack those inputs and
the porter's blessed lowering (parity-or-reject on a missing member) would drop
the node -- making the compiled blessed-method feature DOA.

The fix: the extractor unions in each blessed method's declared ``reads`` (the
preset attrs its interpreted adapter reads) whenever the compute CALLS that
method. This suite proves the union lands the presets on ``spec['inputs']`` and
does NOT over-capture for a plain (non-blessed) compute.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# A blessed compute: calls the two blessed methods; it never names the presets
# they read (colorSpace / wrapModeU / borderColor / ...) textually. u/v are
# passed as literals so no undeclared user attrs are referenced.
_BLESSED_COMPUTE = (
    "buf = self.read_texture()\n"
    "r, g, b, a = self.sample_texture(buf, 0.5, 0.25)\n"
    "self.outColor = (r, g, b)\n"
    "self.outAlpha = a\n"
)

# The union of presets the two blessed adapters (file_methods.read_texture +
# sample_texture) read -- these MUST land on the compiled spec's inputs.
_EXPECTED_READS = (
    "fileName", "colorSpace", "preFilter", "preFilterKernel", "preFilterRadius",
    "wrapModeU", "wrapModeV", "borderColor",
)


def _spec_for(compute):
    """Create an mPyFile with the given compute (empty init to isolate the
    compute-driven capture) and extract its porter spec."""
    import maya.cmds as cmds
    from mpynode.wrappers.mpy_file import MPyFile
    from mpynode.native.spec import spec_extractor

    cmds.file(new=True, force=True)
    w = MPyFile.create(name="blessedFile#")
    w.set_init_expression("")
    w.set_compute_expression(compute)
    return spec_extractor.extract_spec(w.get_name())


class TestBlessedPresetCapture(unittest.TestCase):
    def test_blessed_reads_are_captured(self):
        spec   = _spec_for(_BLESSED_COMPUTE)
        inputs = spec.get("inputs") or {}
        for nm in _EXPECTED_READS:
            self.assertIn(
                nm, inputs,
                "blessed compute reads %r inside self.read_texture/"
                "self.sample_texture but the extractor did not capture it "
                "(inputs=%s)" % (nm, sorted(inputs)))

    def test_plain_compute_does_not_pull_blessed_reads(self):
        # A plain mPyFile that never calls a blessed method must NOT get the
        # blessed reads injected solely by this mechanism (over-capture guard).
        spec   = _spec_for("self.outAlpha = 0.0\n")
        inputs = spec.get("inputs") or {}
        for nm in ("colorSpace", "wrapModeU", "wrapModeV", "borderColor",
                   "preFilter", "preFilterKernel", "preFilterRadius"):
            self.assertNotIn(
                nm, inputs,
                "plain compute (no blessed call) pulled in preset %r via the "
                "blessed-reads mechanism (over-capture)" % nm)


if __name__ == "__main__":
    unittest.main()
