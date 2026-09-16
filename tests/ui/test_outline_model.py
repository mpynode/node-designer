import unittest
from mpynode._common.methods.outline_model import build_outline, OUTLINE_GROUPS
SRC = (
    "import os\n"
    "def helper(x):\n"
    "    return x\n"
    "from mpynode._common.methods.maya_command import maya_command, maya_demo\n"
    "@maya_command(name='doThing')\n"
    "def do_thing(self, a, b=2):\n"
    "    return a\n"
    "@maya_demo(label='My Demo')\n"
    "def demo_it(self):\n"
    "    return 1\n"
    "def setup(self, selection=None):\n"
    "    return selection\n"
    "@staticmethod\n"
    "def util():\n"
    "    return 3\n"
    "def plain_method(self):\n"
    "    return 4\n"
)
class TestBuildOutline(unittest.TestCase):
    def _by_kind(self, items):
        d = {}
        for it in items:
            d.setdefault(it.kind, []).append(it.name)
        return d
    def test_groups(self):
        items = build_outline(SRC)
        d     = self._by_kind(items)
        self.assertEqual(d.get("Commands"), ["doThing"])
        self.assertEqual(d.get("Demos"),    ["My Demo"])
        self.assertEqual(d.get("Setup"),    ["setup"])
        self.assertEqual(d.get("Static"),   ["util"])
        self.assertEqual(d.get("Instance"), ["plain_method"])
        self.assertEqual(d.get("Module"),   ["helper"])
    def test_command_params_and_runnable(self):
        items = build_outline(SRC)
        cmd   = [it for it in items if it.kind == "Commands"][0]
        self.assertTrue(cmd.runnable)
        self.assertEqual(cmd.run_kind, "command")
        self.assertIn("a", cmd.params)
    def test_syntax_error_returns_none(self):
        self.assertIsNone(build_outline("def broken(:\n"))
    def test_empty_returns_empty_list(self):
        self.assertEqual(build_outline(""), [])
    def test_lineno_present(self):
        for it in build_outline(SRC):
            self.assertGreater(it.lineno, 0)


# A source exercising all three method kinds (instance / classmethod / static)
# plus a cls-first factory-by-convention (no decorator).
CLS_SRC = (
    "def freefunc(x):\n"
    "    return x\n"
    "@classmethod\n"
    "def make(cls):\n"
    "    return cls\n"
    "def make_by_convention(cls, n):\n"
    "    return n\n"
    "@staticmethod\n"
    "def util():\n"
    "    return 3\n"
    "def plain(self):\n"
    "    return 1\n"
)


class TestClassmethodBucket(unittest.TestCase):
    """@classmethod / cls-first defs get their OWN 'Classmethod' kind and are no
    longer mislabeled 'Instance' (the pre-fix behaviour)."""

    def _by_kind(self, items):
        d = {}
        for it in items:
            d.setdefault(it.kind, []).append(it.name)
        return d

    def test_classmethod_and_cls_first_bucketed(self):
        d = self._by_kind(build_outline(CLS_SRC))
        self.assertEqual(sorted(d.get("Classmethod", [])),
                         ["make", "make_by_convention"])
        self.assertEqual(d.get("Static"), ["util"])
        self.assertEqual(d.get("Instance"), ["plain"])
        self.assertNotIn("make", d.get("Instance", []))
        self.assertNotIn("make_by_convention", d.get("Instance", []))


class TestGroupMetadata(unittest.TestCase):
    """OUTLINE_GROUPS carries the new Classmethod kind; GROUP_LABELS gives every
    kind a human display label; ALWAYS_SHOWN_GROUPS is a subset of the kinds."""

    def test_classmethod_in_groups(self):
        self.assertIn("Classmethod", OUTLINE_GROUPS)

    def test_labels_cover_all_kinds(self):
        from mpynode._common.methods.outline_model import (
            GROUP_LABELS, ALWAYS_SHOWN_GROUPS)
        for g in OUTLINE_GROUPS:
            self.assertIn(g, GROUP_LABELS)
            self.assertTrue(GROUP_LABELS[g])
        for g in ALWAYS_SHOWN_GROUPS:
            self.assertIn(g, OUTLINE_GROUPS)

    def test_method_labels_read_clearly(self):
        from mpynode._common.methods.outline_model import GROUP_LABELS
        self.assertEqual(GROUP_LABELS["Instance"],    "Instance Methods")
        self.assertEqual(GROUP_LABELS["Classmethod"], "Class Methods")
        self.assertEqual(GROUP_LABELS["Static"],      "Static Methods")
        self.assertEqual(GROUP_LABELS["Module"],      "Functions")

    def test_sort_never_keyerrors_on_new_kind(self):
        # build_outline sorts by order[kind]; a Classmethod item must sort fine.
        items = build_outline(CLS_SRC)
        self.assertIsNotNone(items)
        self.assertTrue(any(it.kind == "Classmethod" for it in items))


class TestCommandTemplates(unittest.TestCase):
    """``is_used`` on the offered command TEMPLATE rows.

    mPyBlendShape is the only seed that ships templates. Its three, as
    ``(command name, def name)``::

        ('add_targets', 'add_targets')
        ('load_target', 'load_target_cmd')
        ('load_shapes', 'load_shapes_cmd')

    A template is used when the buffer carries it by EITHER name -- the same
    two-part identity ``call_command`` resolves by (``methods_registry.py:478``)
    and the compile refuses duplicates of (``command_companion.py:269-281``).
    """

    TYPE = "mPyBlendShape"

    def _used(self, src):
        items = build_outline(src, self.TYPE) or []
        return {it.name: it.is_used
                for it in items if it.run_kind == "template"}

    def test_no_source_offers_every_template(self):
        self.assertEqual(
            self._used(""),
            {"add_targets": False, "load_target": False, "load_shapes": False})

    def test_pasted_verbatim_is_used(self):
        used = self._used("@maya_command\n"
                          "def add_targets(self, m=None):\n"
                          "    return []\n")
        self.assertTrue(used["add_targets"])
        self.assertFalse(used["load_target"])

    def test_renaming_the_command_keeps_the_template_used(self):
        """THE REGRESSION. The def is right there, so re-offering the template
        told the user their def did not exist. Renaming the command is the
        workflow the template's own "rename me" comment asks for."""
        used = self._used('@maya_command(name="stub")\n'
                          "def add_targets(self, m=None):\n"
                          "    return []\n")
        self.assertTrue(used["add_targets"])

    def test_renaming_the_command_on_a_suffixed_template(self):
        """Same defect where the template's def name differs from its command
        name -- the command-name-only rule matched neither."""
        used = self._used('@maya_command(name="faceLoadTarget")\n'
                          "def load_target_cmd(self, path):\n"
                          "    return None\n")
        self.assertTrue(used["load_target"])
        self.assertFalse(used["load_shapes"])

    def test_an_undecorated_def_of_the_same_name_counts(self):
        """No decorator at all: the module-scope name is still taken, and
        pasting would shadow it."""
        used = self._used("def add_targets(self, m=None):\n"
                          "    return []\n")
        self.assertTrue(used["add_targets"])

    def test_the_command_name_clause_still_holds(self):
        """The mirror: def renamed, command name kept. Offering the template
        here would let the user register a SECOND command of that name, which
        the compile refuses (command_companion.py:269)."""
        used = self._used('@maya_command(name="add_targets")\n'
                          "def my_adder(self, m=None):\n"
                          "    return []\n")
        self.assertTrue(used["add_targets"])

    def test_a_class_scoped_def_does_not_count(self):
        used = self._used("class Helper(object):\n"
                          "    def add_targets(self, m=None):\n"
                          "        pass\n")
        self.assertFalse(used["add_targets"])

    def test_a_nested_def_does_not_count(self):
        used = self._used("def outer(self):\n"
                          "    def add_targets(m=None):\n"
                          "        pass\n"
                          "    return add_targets\n")
        self.assertFalse(used["add_targets"])

    def test_no_native_type_yields_no_template_rows(self):
        """Every other build_outline caller passes one arg and must be
        completely unaffected."""
        items = build_outline("def only(self):\n    return 1\n")
        self.assertEqual(
            [it for it in items if it.run_kind == "template"], [])


if __name__ == "__main__":
    unittest.main()
