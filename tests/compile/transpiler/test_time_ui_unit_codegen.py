"""Every compiled time WRITE names the UI time unit.

A bare ``MTime(x)`` is kFilm (24 fps, MTime.h), while the interpreted writer
is ``MTime(x, MTime.uiUnit())`` and every compiled time READ
(``asTime()`` / ``asMTime().value()``) comes back IN the UI unit. Measured on a
scratch node at ntsc: frame 10 + 2 read 12.0 interpreted and 15.0 compiled.
The porter hints called the value seconds; it is frames in the UI unit.
"""
from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _spec(inputs, outputs, compute="", base="MPxNode", mpy_type="mPyNode"):
    def side(d):
        return {k: {"type": t, "is_array": arr} for k, (t, arr) in d.items()}

    return {
        "suggested": {"node_type_name": "timeProbe", "class_name": "TimeProbe",
                      "type_id": "0x0007FF43", "mpx_base": base},
        "mpy_type":    mpy_type,
        "source_node": "timeProbeSrc",
        "inputs":      side(inputs),
        "outputs":     side(outputs),
        "portability": {"portable": True, "blockers": []},
        "compute":     compute,
        "init":        "",
        "variables":   {},
    }


class TestWrites(unittest.TestCase):

    def test_emitter_tables(self):
        from mpynode.native.compiler import emit_attr

        self.assertEqual(emit_attr._elem_set_stmt("time", "v"),
                         "eh.setMTime(MTime(v, MTime::uiUnit()));")
        self.assertEqual(emit_attr._OUT_DEFAULT["time"] % "h",
                         "h.setMTime(MTime(0.0, MTime::uiUnit()));")
        hint = emit_attr._setter_hint({"member": "aT", "meta": {"type": "time"}})
        self.assertEqual(hint, "h_aT.setMTime(MTime(<frames>, MTime::uiUnit()))")

    def test_lowered_node_writes_every_time_in_the_ui_unit(self):
        from mpynode.native import compiler as codegen

        cpp = codegen.generate_cpp(
            _spec({"t": ("time", False)},
                  {"tOut": ("time", False), "tArr": ("time", True),
                   "frame": ("double", False)},
                  compute=("self.tOut = self.t + 2.0\n"
                           "self.tArr = [self.t, self.t * 2.0]\n"
                           "self.frame = self.t\n")),
            for_port=True)
        self.assertNotIn(codegen.PORT_BEGIN, cpp)
        self.assertIn("h_aTOut.setMTime(MTime((double)(", cpp)
        writes = re.findall(r"setMTime\(MTime\(.*\);", cpp)
        self.assertGreaterEqual(len(writes), 4, writes)  # seed, write, element, gap
        for w in writes:
            self.assertIn("MTime::uiUnit())", w)

    def test_ported_node_hint_says_frames(self):
        from mpynode.native import compiler as codegen

        cpp = codegen.generate_cpp(
            _spec({"t": ("time", False)}, {"tOut": ("time", False)},
                  compute="import os\nself.tOut = float(len(os.listdir('.')))\n"),
            for_port=True)
        self.assertIn("MTime(<frames>, MTime::uiUnit())", cpp)
        self.assertNotIn("<seconds>", cpp)


class TestReadHints(unittest.TestCase):
    """transform / locator / IK solver describe a time input's local to the
    porter: it is frames in the UI unit (asMTime().value()), never seconds."""

    def test_family_hints(self):
        from mpynode.native.compiler import emit_iksolver, emit_locator, emit_transform

        for hint in (emit_transform._generic_local_hint("time"),
                     emit_locator._loc_generic_hint("time"),
                     emit_iksolver._ik_generic_local_hint("time")):
            self.assertEqual(hint, "double, frames (UI time unit)")


if __name__ == "__main__":
    unittest.main()
