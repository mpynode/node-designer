"""mPyBlendShape base-class facts and the rationale that documents them.

``mPyBlendShape`` derives ``MPxDeformerNode``, and four places used to
explain that choice with the claim that ``MPxBlendShape`` "is API 2.0 only
and not exposed in this build". That claim is INVERTED: ``MPxBlendShape``
ships in API **1.0** (``maya.OpenMayaMPx``) and does NOT exist in API 2.0,
on both Maya 2024 and 2026.

``test_mpxblendshape_is_exposed_in_api1_not_api2`` pins the fact itself, so
the prose check below can never outlive the API it describes.
"""

from __future__ import annotations

import os
import unittest

from ._setup import standalone_init


def setUpModule():
    standalone_init()


def _repo_root() -> str:
    # .../scripts/mpynode/_tests/this_file.py -> repo root
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(os.path.dirname(here)))


# The files that explain WHY mPyBlendShape is not on MPxBlendShape.
RATIONALE_SOURCES = (
    os.path.join("scripts", "mpynode", "_api1", "mpy_blend_shape.py"),
    os.path.join("scripts", "mpynode", "wrappers", "mpy_blend_shape.py"),
    os.path.join("docs", "node_types", "mPyBlendShape.md"),
    os.path.join("scripts", "mpynode", "_node_registry.py"),
    # Carried the same inverted claim; corrected at integration.
    os.path.join("plug-ins", "mpynode_api1.py"),
    os.path.join("docs", "ARCHITECTURE.md"),
)

# Spellings of the inverted claim, lowercased. ``api 2.0-only`` (space then
# hyphen) is ARCHITECTURE.md's house style and was the spelling that slipped
# past the first version of this list.
_API2_ONLY_SPELLINGS = ("api 2.0 only", "api 2.0-only", "api-2.0-only",
                        "api-2.0 only", "api2-only", "api2 only")


class TestMPxBlendShapeAvailability(unittest.TestCase):
    """Ground truth. Verified on Maya 2024 and 2026."""

    def test_mpxblendshape_is_exposed_in_api1_not_api2(self):
        import maya.OpenMayaMPx as ommpx

        self.assertTrue(
            hasattr(ommpx, "MPxBlendShape"),
            "maya.OpenMayaMPx.MPxBlendShape should exist (api1)",
        )

        import maya.api.OpenMaya as om2
        import maya.api.OpenMayaAnim as oma2

        self.assertFalse(hasattr(om2, "MPxBlendShape"),
                         "api2 OpenMaya should NOT expose MPxBlendShape")
        self.assertFalse(hasattr(oma2, "MPxBlendShape"),
                         "api2 OpenMayaAnim should NOT expose MPxBlendShape")

        # The proxy classification exists on both generations.
        self.assertEqual(ommpx.MPxNode.kBlendShape, 25)


class TestBlendShapeRationale(unittest.TestCase):
    """The recorded rationale must not contradict the API it describes."""

    def _sources(self):
        root = _repo_root()
        for rel in RATIONALE_SOURCES:
            path = os.path.join(root, rel)
            self.assertTrue(os.path.isfile(path), "missing %s" % rel)
            with open(path, "r", encoding="utf-8") as fh:
                yield rel, fh.read()

    def test_no_source_claims_mpxblendshape_is_api2_only(self):
        import maya.OpenMayaMPx as ommpx
        import maya.api.OpenMayaAnim as oma2

        # Only meaningful while the inversion holds. If Autodesk ever moves
        # the class, this test steps aside instead of pinning stale prose.
        if not hasattr(ommpx, "MPxBlendShape"):
            self.skipTest("api1 no longer exposes MPxBlendShape")
        if hasattr(oma2, "MPxBlendShape"):
            self.skipTest("api2 now exposes MPxBlendShape")

        # A match counts only when ``blendshape`` is named within +-2 lines of
        # it. Two general-purpose files are scanned now, and ARCHITECTURE.md
        # carries a separate TRUE sentence ("api2 only exposes `MPxNode`,
        # `MPxSurfaceShape`, ...") that an unscoped scan reports as an offender.
        # The window (not the line) is what keeps the claim itself in range:
        # the prose wraps, so the spelling and the class name land on different
        # lines (docs/node_types/mPyBlendShape.md:13-14 is exactly that shape).
        offenders = []
        for rel, text in self._sources():
            lines = text.splitlines()
            for n, raw in enumerate(lines, 1):
                low = raw.lower()
                hits = [s for s in _API2_ONLY_SPELLINGS if s in low]
                if not hits:
                    continue
                window = "\n".join(lines[max(0, n - 3):n + 2]).lower()
                if "blendshape" not in window:
                    continue
                for spelling in hits:
                    offenders.append("%s:%d (%r)" % (rel, n, spelling))

        self.assertEqual(
            offenders, [],
            "MPxBlendShape ships in API 1.0, not 2.0 -- these sites state "
            "the inverse: %s" % ", ".join(offenders),
        )

    def test_registry_native_class_matches_the_real_base(self):
        """The Init header's "wraps" line must name the actual base class."""
        from mpynode._api1.mpy_blend_shape import MPyBlendShape as Api1Class
        from mpynode._node_registry import REGISTRY

        spec = REGISTRY["mPyBlendShape"]
        actual_base = Api1Class.__bases__[0]
        expected = "%s.%s" % (actual_base.__module__.replace(
            "maya.OpenMayaMPx", "maya.OpenMayaMPx"), actual_base.__name__)
        self.assertTrue(
            spec.native_class.endswith("." + actual_base.__name__),
            "registry native_class %r does not name the real base %r "
            "(expected something ending in .%s)"
            % (spec.native_class, expected, actual_base.__name__),
        )


if __name__ == "__main__":
    unittest.main()
