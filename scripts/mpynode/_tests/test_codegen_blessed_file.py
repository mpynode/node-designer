"""Blessed texture methods lower to the hand-written C++ kernels in a real
``generate_cpp()`` TU (Task 4.2 / 4.3; needs Maya standalone for the codegen
attr machinery).

A compiled mPyFile whose custom compute calls ``self.read_texture()`` /
``self.sample_texture()`` lowers DETERMINISTICALLY -- the TU carries the verified
nd_tex_* kernels + the ``NdTexCache`` member and has NO AI PORT region. A blessed
compute that does NOT fully lower is an honest reject (never an AI-port).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from ._setup import standalone_init, ensure_plugins_loaded


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# int (not enum) presets keep the hand-authored spec free of enum_names; the
# blessed lowering casts each with (int)/(bool)/(float) exactly like the
# interpreted adapter, so parity holds regardless of the Maya attr kind.
_INPUTS = {
    "fileName": {"type": "string", "is_array": False},
    "colorSpace": {"type": "int", "is_array": False},
    "preFilter": {"type": "bool", "is_array": False},
    "preFilterKernel": {"type": "int", "is_array": False},
    "preFilterRadius": {"type": "float", "is_array": False},
    "wrapModeU": {"type": "int", "is_array": False},
    "wrapModeV": {"type": "int", "is_array": False},
    "borderColor": {"type": "color", "is_array": False},
    "u": {"type": "float", "is_array": False},
    "v": {"type": "float", "is_array": False},
}
_OUTPUTS = {
    "outR": {"type": "float", "is_array": False},
    "outG": {"type": "float", "is_array": False},
    "outB": {"type": "float", "is_array": False},
    "outA": {"type": "float", "is_array": False},
}


def _spec(compute):
    return {
        "schema_version": 1, "source_node": "blessedFile",
        "mpy_type": "mPyFile",
        "suggested": {"node_type_name": "blessedFileNode",
                      "class_name": "BlessedFileNode",
                      "type_id": "0x00070310",
                      "mpx_base": "MPxNode"},
        "inputs": dict(_INPUTS), "outputs": dict(_OUTPUTS),
        "compute": compute, "init": "import numpy as np\n",
        "portability": {"portable": True, "blockers": [], "warnings": [],
                        "reads_image_file": False},
    }


_LOWERABLE = (
    "buf = self.read_texture()\n"
    "r, g, b, a = self.sample_texture(buf, self.u, self.v)\n"
    "self.outR = r\n"
    "self.outG = g\n"
    "self.outB = b\n"
    "self.outA = a\n"
)

# read_texture() (blessed) THEN an unsupported construct so the whole compute
# cannot fully lower. np.linalg.pinv is the construct: it needs a GENERAL svd
# and nd::svd is 3x3-only, so there is nothing deterministic to build it on.
# This was np.linalg.solve until solve gained a deterministic nd::solve
# lowering -- if pinv ever lowers too, swap in another rejected construct
# rather than deleting the test; what it guards is the honest-reject path, not
# any particular function.
_UNLOWERABLE = (
    "buf = self.read_texture()\n"
    "bad = np.linalg.pinv(np.eye(3))\n"
    "self.outR = float(bad[0][0])\n"
    "self.outG = 0.0\n"
    "self.outB = 0.0\n"
    "self.outA = 1.0\n"
)


class TestBlessedFileCodegen(unittest.TestCase):
    def test_blessed_compute_lowers_deterministically(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(_spec(_LOWERABLE), for_port=True)
        self.assertIn("nd_tex_load_linear", cpp)     # verified load kernel present
        self.assertIn("NdTexCache _texCache", cpp)   # per-instance cache member
        self.assertIn("nd_tex_sample", cpp)          # verified sampler present
        self.assertNotIn(codegen.PORT_BEGIN, cpp)    # blessed lowered -> no AI port

    def test_blessed_compute_that_wont_lower_is_honest_reject(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler.errors import UnsupportedSpec
        with self.assertRaises(UnsupportedSpec):
            codegen.generate_cpp(_spec(_UNLOWERABLE), for_port=True)


if __name__ == "__main__":
    unittest.main()
