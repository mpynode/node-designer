"""No test renders into the user's Maya project.

``ogsRender`` takes no output path: it writes into the current project's
images folder, which is the user's default Maya project unless a test opens
another. Every test function that calls ``ogsRender`` must open a throwaway
project first (``workspace(<dir>, openWorkspace=True)``), and every
``playblast`` call must name its ``filename``.
"""

from __future__ import annotations

import tests  # noqa: F401 -- first: keeps the run out of ~/.mpynode

import ast
import os
import unittest

_TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _call_name(node):
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _keywords(node):
    return {kw.arg for kw in node.keywords if kw.arg}


def _opens_workspace(func):
    for node in ast.walk(func):
        if (isinstance(node, ast.Call)
                and _call_name(node) == "workspace"
                and "openWorkspace" in _keywords(node)):
            return True
    return False


def render_offenders(source, label):
    """Return ``label:line`` for each render call that would write into the
    current project."""
    offenders = []
    tree      = ast.parse(source)
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name == "ogsRender" and not _opens_workspace(func):
                offenders.append("%s:%d" % (label, node.lineno))
            elif name == "playblast" and "filename" not in _keywords(node):
                offenders.append("%s:%d" % (label, node.lineno))
    return sorted(set(offenders))


class TestRenderOutputHygiene(unittest.TestCase):

    def test_no_test_renders_into_the_current_project(self):
        offenders = []
        for folder, _dirs, files in os.walk(_TESTS):
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                label = os.path.relpath(path, _TESTS)
                offenders.extend(render_offenders(source, label))
        self.assertEqual(offenders, [])

    def test_a_bare_ogsrender_is_reported(self):
        source = (
            "def test_x():\n"
            "    mc.ogsRender(camera='persp')\n"
        )
        self.assertEqual(render_offenders(source, "t.py"), ["t.py:2"])

    def test_an_ogsrender_in_a_throwaway_project_passes(self):
        source = (
            "def test_x():\n"
            "    mc.workspace(d, openWorkspace=True)\n"
            "    mc.ogsRender(camera='persp')\n"
        )
        self.assertEqual(render_offenders(source, "t.py"), [])

    def test_a_playblast_without_a_filename_is_reported(self):
        source = (
            "def test_x():\n"
            "    mc.playblast(format='image')\n"
            "    mc.playblast(format='image', filename=p)\n"
        )
        self.assertEqual(render_offenders(source, "t.py"), ["t.py:2"])


if __name__ == "__main__":
    unittest.main()
