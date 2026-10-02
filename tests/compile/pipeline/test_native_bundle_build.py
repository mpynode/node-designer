"""The bundle CLI, end to end: two small nodes compiled, linked, loaded.

Needs a Maya devkit and a C++ toolchain, so it skips wherever the other
compiled-node tests skip. Everything text-only lives in ``test_native_bundle``.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

from tests.compile.pipeline.test_native_bundle import _src, _write


def _running_maya_root():
    from mpynode.native.toolchain import toolchain

    return toolchain.running_maya_dir()


class TestBundleCliBuildsAndLoads(unittest.TestCase):

    def test_two_nodes_become_one_plugin_that_loads(self):
        from mpynode.native import bundle
        from mpynode.native.compiler import bundler

        maya = _running_maya_root()
        if maya is None:
            self.skipTest("no Maya devkit headers on this host")
        if bundler._prepare_compiler({"reason": ""}, True) is None:
            self.skipTest("no C++ toolchain on this host")

        # tempfile lands on local disk, which the linker needs (a streamed
        # drive hangs link.exe).
        d   = tempfile.mkdtemp(prefix="bundle_e2e_")
        a   = _write(d, "in/aNode.cpp", _src("aNode", "ANode", "0x00081010"))
        b   = _write(d, "in/bNode.cpp", _src("bNode", "BNode", "0x00081011"))
        out = os.path.join(d, "duo")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = bundle.main(["duo", a, b, "--maya", maya, "--out", out])
        text = buf.getvalue()
        self.assertEqual(rc, 0, text)
        self.assertIn("load check: ok -- 2 type(s)", text)
        from mpynode.native.toolchain import toolchain

        # In the folder named after the Maya it was built for; the file name
        # carries no version (Maya records it in every scene).
        year = toolchain.maya_year(maya)
        self.assertTrue(os.path.isfile(os.path.join(out, year, "duo" + toolchain.plugin_ext())))
        self.assertTrue(os.path.isfile(os.path.join(out, "build", "manifest.json")))


if __name__ == "__main__":
    unittest.main()
