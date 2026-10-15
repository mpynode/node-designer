"""A compiled locator redraws as the interpreted mPyLocator does (v44).

The interpreted node (``_api2/mpy_locator.py``) overrides setDependentsDirty:
a suspended node (nodeState Has No Effect / Blocking) forwards nothing, and a
dirtied user input -- a compound child or an array element counting as its
root -- calls ``MRenderer.setGeometryDrawDirty``. None of its attrs carries
affectsAppearance.

Until v44 the compiled locator did the opposite: no override, and
``setAffectsAppearance(true)`` on every input (38 inputs in the 5 shipped
locators). These tests pin the generator, every shipped lineage file, and the
interpreted reference the compiled side copies. A headless session cannot
show a redraw, so the redraw itself is checked by hand in GUI Maya.
"""
from __future__ import annotations

import glob
import json
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# (template folder, node type) for every shipped compiled locator
_LOCATORS = (("Animated Selection", "animatedSelection"),
             ("Animated Text", "animatedText"),
             ("Circular Text", "circularText"),
             ("Mesh Regions", "meshRegionLocator"),
             ("Widget Showcase", "widgetShowcase"))

_DEF = "::setDependentsDirty(const MPlug& plug, MPlugArray& affected) {"


def _read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read().replace("\r\n", "\n")


def _spec(template):
    man = os.path.join(_paths.ROOT, "templates", "MPyLocator", template,
                       "build", "manifest.json")
    with open(man, encoding="utf-8") as fh:
        return json.load(fh)["nodes"][0]["spec"]


def _cpp(template):
    from mpynode.native import compiler as codegen

    return codegen.generate_cpp(_spec(template), for_port=True)


def _redraw(cpp):
    """The setDependentsDirty definition, from its signature to its brace."""
    start = cpp.index(_DEF)
    end   = cpp.index("\n}\n", start)
    return cpp[start:end + 2]


def _triggers(cpp):
    """The attr members the override redraws for."""
    return set(re.findall(r"attr == (\w+)", _redraw(cpp)))


def _member(cpp, plug):
    """The static MObject the plug's create() assigns."""
    m = re.search(r"(\w+) = \w+\.create\w*\(\"%s\"" % re.escape(plug), cpp)
    return m.group(1)


def _lineage(build, node_type):
    """Every shipped lineage file of ``node_type`` under ``build``: stage 1,
    the AI port, optimizer rounds, the final and the plug-in source."""
    out = glob.glob(os.path.join(build, "stages", node_type, "**", "*.cpp"),
                    recursive=True)
    for p in (os.path.join(build, node_type, node_type + ".cpp"),
              os.path.join(build, "source", node_type + ".cpp")):
        if os.path.isfile(p):
            out.append(p)
    return sorted(out)


class TestGeneratedLocator(unittest.TestCase):
    """The stage-1 codegen of each shipped locator."""

    def test_every_user_input_is_a_redraw_trigger(self):
        total = 0
        for tpl, _ty in _LOCATORS:
            with self.subTest(template=tpl):
                cpp  = _cpp(tpl)
                want = {_member(cpp, p) for p in _spec(tpl)["inputs"]}
                self.assertEqual(_triggers(cpp), want)
                total += len(want)
        self.assertEqual(total, 38)

    def test_no_input_carries_affects_appearance(self):
        for tpl, _ty in _LOCATORS:
            with self.subTest(template=tpl):
                self.assertNotIn("setAffectsAppearance", _cpp(tpl))

    def test_a_suspended_node_forwards_nothing(self):
        # the nodeState gate runs before any trigger, and a nodeState change
        # drops the cached fact instead of redrawing
        body = _redraw(_cpp("Circular Text"))
        gate = body.index("if (m_suspended) return MS::kSuccess;")
        self.assertLess(body.index("if (plug.attribute() == MPxNode::state) {\n"
                                   "        m_suspended = -1;\n"
                                   "        return MS::kSuccess;"), gate)
        self.assertLess(gate, body.index("attr == "))
        self.assertLess(gate, body.index("setGeometryDrawDirty"))

    def test_a_child_or_element_counts_as_its_root(self):
        body = _redraw(_cpp("Mesh Regions"))
        self.assertIn("    while (root.isChild() || root.isElement())\n"
                      "        root = root.isElement() ? root.array() "
                      ": root.parent();\n"
                      "    const MObject attr = root.attribute();", body)

    def test_the_override_is_declared_on_the_node(self):
        for tpl, _ty in _LOCATORS:
            with self.subTest(template=tpl):
                self.assertIn("    MStatus setDependentsDirty(const MPlug& "
                              "plug, MPlugArray& affected) override;",
                              _cpp(tpl))


class TestShippedLocators(unittest.TestCase):
    """Every shipped lineage file carries the stage-1 override verbatim."""

    def _builds(self, ty):
        tpl = dict((t, f) for f, t in _LOCATORS)[ty]
        return (os.path.join(_paths.ROOT, "templates", "MPyLocator", tpl,
                             "build"),
                os.path.join(_paths.ROOT, "templates", "All Templates Plugin",
                             "build"))

    def test_every_lineage_file_redraws_as_stage_1(self):
        seen = 0
        for _tpl, ty in _LOCATORS:
            for build in self._builds(ty):
                stage1 = _read(os.path.join(build, "stages", ty,
                                            "1_transpiled.cpp"))
                want = _redraw(stage1)
                for path in _lineage(build, ty):
                    with self.subTest(file=os.path.relpath(path,
                                                           _paths.ROOT)):
                        text = _read(path)
                        self.assertNotIn("setAffectsAppearance", text)
                        self.assertIn(want, text)
                        seen += 1
        # 5 templates (stage 1 + their lineage) and the All Templates copies
        self.assertEqual(seen, 38)

    def test_shipped_stage_1_triggers_every_input(self):
        for tpl, ty in _LOCATORS:
            with self.subTest(template=tpl):
                stage1 = _read(os.path.join(self._builds(ty)[0], "stages", ty,
                                            "1_transpiled.cpp"))
                want = {_member(stage1, p) for p in _spec(tpl)["inputs"]}
                self.assertEqual(_triggers(stage1), want)


class TestInterpretedReference(unittest.TestCase):
    """What the compiled side copies, read off the interpreted node."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _user_node(self, name):
        import maya.api.OpenMaya as om

        obj = om.MSelectionList().add(name).getDependNode(0)
        return om.MFnDependencyNode(obj).userNode(), obj

    def test_a_user_input_does_not_affect_appearance(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        w = MPyLocator.create(name="redrawRef")
        n = w.get_name()
        w.add_input_attr("offset", "float")
        w.add_input_attr("tint", "color")
        for attr in ("offset", "tint", "tintR"):
            self.assertFalse(mc.attributeQuery(attr, node=n,
                                               affectsAppearance=True), attr)

    def test_a_user_input_and_its_child_redraw(self):
        import maya.api.OpenMaya as om
        from mpynode.wrappers.mpy_locator import MPyLocator

        w = MPyLocator.create(name="redrawRef")
        w.add_input_attr("offset", "float")
        w.add_input_attr("tint", "color")
        node, obj = self._user_node(w.get_name())
        fn = om.MFnDependencyNode(obj)
        self.assertTrue(node._is_draw_dirty_trigger(fn.findPlug("offset", True)))
        self.assertTrue(node._is_draw_dirty_trigger(fn.findPlug("tintR", True)))
        self.assertFalse(node._is_draw_dirty_trigger(
            fn.findPlug("visibility", True)))


if __name__ == "__main__":
    unittest.main()
