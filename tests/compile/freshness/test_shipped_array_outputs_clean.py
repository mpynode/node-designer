"""Every array output a SHIPPED compiled node writes is cleaned at the attribute.

``emit_attr._array_write_lines`` writes an array output and then cleans it
twice: ``setAllClean()`` for the elements and ``data.setClean(<attr>)`` for the
attribute (recipe 34). Without the second, the Evaluation Manager called
compute once per connected array output -- Spine 3 times a frame, DNET twice
with its solver drifting from DG -- and nothing else would notice: parity sees
identical values and the optimizer bench pulls a single element.

``test_shipped_artifact_freshness`` checks that a final keeps every clean its
stage 1 has; this checks the finals themselves, in both trees: every template's
``build/<type>/<type>.cpp`` and every All Templates Plugin source. An array
written through ``data.outputArrayValue(aX)`` must be marked clean somewhere in
the same file, through any datablock receiver. Deformers write their geometry
through ``block.outputArrayValue(outputGeom)`` and clean it per element, which
is correct for them, so the ``data.`` receiver keeps them out of scope.
"""

from __future__ import annotations

import glob
import os
import re
import unittest

from tests import _paths

_TEMPLATES = os.path.join(_paths.ROOT, "templates")
_MEGA_SRC  = os.path.join(_TEMPLATES, "All Templates Plugin", "build", "source")
_WRITES    = re.compile(r"\bdata\.outputArrayValue\(\s*(a\w+)\s*[,)]")

# Six array-output templates plus aimTransform, in each tree. Below this the
# scan has gone vacuous (a moved tree, a renamed member), not green.
_FLOOR = 7


def _finals():
    """Each template's shipped ``build/<type>/<type>.cpp`` (not the mega tree)."""
    out = []
    for path in glob.glob(os.path.join(_TEMPLATES, "*", "*", "build", "*", "*.cpp")):
        if os.path.basename(path) == os.path.basename(os.path.dirname(path)) + ".cpp":
            out.append(path)
    return sorted(out)


def _unclean(paths):
    """``(files writing an array output, [(file, attrs left dirty)])``."""
    from mpynode.native.ai.optimizer_knowledge import _code_only, setclean_targets

    carrying, dirty = 0, []
    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        wrote = set(_WRITES.findall(_code_only(src)))
        if not wrote:
            continue
        carrying += 1
        gone = sorted(wrote - setclean_targets(src))
        if gone:
            dirty.append("%s: %s" % (os.path.relpath(path, _paths.ROOT), ", ".join(gone)))
    return carrying, dirty


class TestShippedArrayOutputsAreClean(unittest.TestCase):

    def _check(self, paths, where):
        carrying, dirty = _unclean(paths)
        self.assertGreaterEqual(carrying, _FLOOR,
                                "only %d %s file(s) write an array output -- the scan "
                                "has gone vacuous" % (carrying, where))
        self.assertEqual(dirty, [],
                         "%s file(s) write an array output without cleaning its "
                         "attribute. Bump PORTER_RECIPE_VERSION and rebuild:\n  %s"
                         % (where, "\n  ".join(dirty)))

    def test_template_finals(self):
        self._check(_finals(), "template")

    def test_all_templates_plugin_sources(self):
        self._check(sorted(glob.glob(os.path.join(_MEGA_SRC, "*.cpp"))), "All Templates Plugin")


if __name__ == "__main__":
    unittest.main()
