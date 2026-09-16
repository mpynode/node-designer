"""Factory (``cls``-first) ``@maya_command`` support — Phase 2 slice 1.

A ``@maya_command`` whose first parameter is ``cls`` is a FACTORY command: it
creates a node rather than operating on one. At runtime ``call_command`` must
bind the wrapper CLASS (not an instance) and return the new node; ``py_export``
must surface it as a real ``@classmethod`` so the exported class is valid Python.
Instance (``self``) commands are unchanged.

See docs/plans/2026-06-23-unified-maya-command-setup-design.md.
"""

from __future__ import annotations

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# read_name proves self-binding; what_cls / what_cls_cm return their first arg so
# the test can assert it is the CLASS (factory) not the instance.
_METHODS = '''@maya_command("readName")
def read_name(self):
    return self.get_name()


@maya_command("whatCls")
def what_cls(cls):
    return cls


@classmethod
@maya_command("whatClsCm")
def what_cls_cm(cls):
    return cls
'''


class TestFactoryRuntime(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode._node_registry import wrap_node

        self.name = mc.createNode("mPyNode", name="host1")
        self.node = wrap_node(self.name, "mPyNode")
        self.node.set_methods_source(_METHODS)

    def test_instance_command_binds_the_instance(self):
        # read_name returns this node's name -> self was bound to the instance.
        self.assertEqual(self.node.call_command("readName"), self.name)

    def test_factory_command_binds_the_class(self):
        result = self.node.call_command("whatCls")
        self.assertIs(result, type(self.node))

    def test_factory_classmethod_form_binds_the_class(self):
        result = self.node.call_command("whatClsCm")
        self.assertIs(result, type(self.node))

    def test_factory_creates_and_returns_a_new_node(self):
        self.node.set_methods_source(
            '@maya_command("mk")\ndef mk(cls):\n'
            '    return cls.create(name="madeByFactory#")\n'
        )
        before  = set(mc.ls(type="mPyNode"))
        created = self.node.call_command("mk")
        after   = set(mc.ls(type="mPyNode"))
        self.assertEqual(len(after - before), 1, "factory must create one node")
        cname = created.get_name() if hasattr(created, "get_name") else str(created)
        self.assertNotEqual(cname, self.name, "must be a NEW node, not the host")


class TestFactoryExport(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode._node_registry import wrap_node

        self.name = mc.createNode("mPyNode", name="exp1")
        self.node = wrap_node(self.name, "mPyNode")

    def _export(self, methods):
        self.node.set_methods_source(methods)
        from mpynode._common.io.py_export import generate_node_script

        return generate_node_script(self.node, class_name="Exp")

    def test_cls_first_surfaces_as_classmethod(self):
        src = self._export(
            '@maya_command("mk")\ndef setup(cls):\n    return cls.create()\n'
        )
        # The surfaced member must be a @classmethod (added since the author
        # omitted it) immediately above the def.
        self.assertRegex(
            src, r"@classmethod\s+@maya_command\(.mk.\)\s+def setup\(cls\)"
        )

    def test_cls_first_with_classmethod_not_doubled(self):
        src = self._export(
            '@classmethod\n@maya_command("mk")\n'
            'def setup(cls):\n    return cls.create()\n'
        )
        self.assertNotRegex(src, r"@classmethod\s+@classmethod")

    def test_self_command_not_made_classmethod(self):
        src = self._export(
            '@maya_command("op")\ndef do_op(self):\n    return self.get_name()\n'
        )
        self.assertNotRegex(
            src, r"@classmethod\s+@maya_command\(.op.\)\s+def do_op\(self\)"
        )


class TestDetectFactoryMetadata(unittest.TestCase):
    """``detect_commands`` must tag each command ``is_factory`` (cls-first or
    @classmethod) -- the single static signal the native codegen, py_export, and
    runtime all use to tell a factory command from a runtime command. ``params``
    must exclude both ``self`` and ``cls`` (neither is a command argument)."""

    def _cmds(self, src):
        from mpynode._common.methods.maya_command import detect_commands

        return {c["func_name"]: c for c in detect_commands(src)}

    def test_self_command_not_factory(self):
        c = self._cmds('@maya_command("op")\ndef op(self, k=1):\n    return k\n')
        self.assertFalse(c["op"]["is_factory"])

    def test_cls_command_is_factory(self):
        c = self._cmds('@maya_command("mk")\ndef mk(cls):\n    return cls\n')
        self.assertTrue(c["mk"]["is_factory"])

    def test_classmethod_command_is_factory(self):
        c = self._cmds(
            '@classmethod\n@maya_command("mk")\ndef mk(cls):\n    return cls\n'
        )
        self.assertTrue(c["mk"]["is_factory"])

    def test_params_exclude_self_and_cls(self):
        c = self._cmds('@maya_command("op")\ndef op(self, a, b=2):\n    return a\n')
        self.assertEqual(c["op"]["params"], ["a", "b"])
        c2 = self._cmds('@maya_command("mk")\ndef mk(cls, x):\n    return x\n')
        self.assertNotIn("cls", c2["mk"]["params"])
        self.assertIn("x", c2["mk"]["params"])

    def test_staticmethod_command_is_static_not_factory(self):
        c = self._cmds(
            '@staticmethod\n@maya_command("s")\ndef s():\n    return 1\n'
        )
        self.assertTrue(c["s"]["is_static"])
        self.assertFalse(c["s"]["is_factory"])

    def test_self_command_not_static(self):
        c = self._cmds('@maya_command("op")\ndef op(self):\n    return 1\n')
        self.assertFalse(c["op"]["is_static"])

    def test_classmethod_command_not_static(self):
        # @classmethod is a factory, never static, even though both are "no self".
        c = self._cmds(
            '@classmethod\n@maya_command("mk")\ndef mk(cls):\n    return cls\n'
        )
        self.assertFalse(c["mk"]["is_static"])
        self.assertTrue(c["mk"]["is_factory"])


if __name__ == "__main__":
    unittest.main()
