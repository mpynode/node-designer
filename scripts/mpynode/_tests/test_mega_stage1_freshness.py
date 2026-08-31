# scripts/mpynode/_tests/test_mega_stage1_freshness.py  (pure -- no setUpModule)
"""The checked-in mega stage-1 artifacts must embed the CURRENT nd_runtime.

``compiled_templates/_combined_plugin/build/stages/<type>/1_transpiled.cpp`` is transpiler
output: ``codegen.generate_cpp(spec, for_port=True)`` with the nd runtime
inlined. Because the runtime is inlined, a runtime fix does NOT reach the
checked-in artifacts -- they keep whatever nd_runtime was current when the mega
build ran, and silently rot.

That is not cosmetic. The artifacts predating the ``nd::maximum_elem`` fix carry
the NaN-DROPPING form of np.minimum/np.maximum (``a > b ? a : b``, which returns
the non-NaN operand when the LEFT one is NaN) at every one of the four min/max
sites -- so anyone reading, hand-finishing or re-compiling a stage-1 file gets
numerics that disagree with numpy and with the shipped runtime.

Refresh them with ``mayapy tools/regen_mega_transpiled.py`` (codegen only -- no
compiler, no linking, no bundle).
"""

from __future__ import annotations

import glob
import os
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
_STAGES = os.path.join(_ROOT, "compiled_templates", "_combined_plugin", "build",
                       "stages")

# The NaN-asymmetric helpers every min/max site must route through.
_HELPERS = ("inline T minimum_elem(", "inline T maximum_elem(")
# Bare, NaN-DROPPING forms -- what the pre-fix runtime emitted.
_NAN_DROPPING = (
    "case BinOp::Min: return a < b ? a : b;",
    "case BinOp::Max: return a > b ? a : b;",
    "return x < y ? x : y;",
    "return x > y ? x : y;",
)


def _stage_files():
    return sorted(glob.glob(os.path.join(_STAGES, "*", "1_transpiled.cpp")))


def _with_nd_runtime():
    """(path, text) for every stage-1 artifact that inlines the nd runtime."""
    out = []
    for path in _stage_files():
        with open(path) as fh:
            text = fh.read()
        if "enum class BinOp" in text:
            out.append((path, text))
    return out


class TestMegaStageOneEmbedsCurrentRuntime(unittest.TestCase):
    def test_the_artifacts_are_actually_on_disk(self):
        """Non-vacuity: without this the assertions below pass on an empty
        glob (e.g. after a path rename)."""
        self.assertGreater(
            len(_stage_files()), 30,
            "found almost no 1_transpiled.cpp under %s" % _STAGES)
        self.assertGreater(
            len(_with_nd_runtime()), 20,
            "almost no stage-1 artifact inlines the nd runtime -- the "
            "min/max assertions below would be vacuous")

    def test_no_artifact_carries_a_nan_dropping_minmax(self):
        offenders = []
        for path, text in _with_nd_runtime():
            hits = [frag for frag in _NAN_DROPPING if frag in text]
            if hits:
                offenders.append("%s: %s"
                                 % (os.path.relpath(path, _ROOT), hits))
        self.assertEqual(
            offenders, [],
            "stale nd_runtime in the checked-in mega stage-1 artifacts -- "
            "np.minimum/np.maximum there DROP a NaN left operand. Refresh "
            "with tools/regen_mega_transpiled.py:\n  "
            + "\n  ".join(offenders))

    def test_every_artifact_routes_through_the_elem_helpers(self):
        missing = []
        for path, text in _with_nd_runtime():
            gaps = [frag for frag in _HELPERS if frag not in text]
            if "case BinOp::Max: return maximum_elem<T>(a, b);" not in text:
                gaps.append("apply_binop Max -> maximum_elem")
            if "case BinOp::Min: return minimum_elem<T>(a, b);" not in text:
                gaps.append("apply_binop Min -> minimum_elem")
            if gaps:
                missing.append("%s: %s"
                               % (os.path.relpath(path, _ROOT), gaps))
        self.assertEqual(
            missing, [],
            "stage-1 artifact does not route min/max through "
            "nd::minimum_elem / nd::maximum_elem:\n  " + "\n  ".join(missing))


if __name__ == "__main__":
    unittest.main()
