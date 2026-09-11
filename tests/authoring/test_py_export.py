"""File ▸ Bake Node to .py File.

``py_export.generate_node_script(py_node)`` emits a standalone Python module
that REBUILDS the node from scratch via the imperative wrapper API -- a
subclass with ``build()`` + ``ls()`` classmethods. These tests run headless
under mayapy; the keystone is a ROUND-TRIP: exec the generated source, call
``build()``, and assert the rebuilt node matches the original (attrs, colors,
expressions). Per the design, persistent stored-var DATA is NOT embedded --
only re-declarations.

The bake is a ONE-WAY trip: the node's Methods become REAL Python (instance
methods, classmethods, module-level free functions) instead of an editable
``_methodsSource`` blob, so the generated script never calls
``set_methods_source`` -- use ``.mpn`` for a full round-trip.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import inspect
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _build_cls(src: str, class_name: str):
    """exec the generated module and return its generated class."""
    ns: dict = {}
    exec(compile(src, "<generated>", "exec"), ns)
    return ns[class_name]


class TestGenerateNodeScript(unittest.TestCase):
    def _gen(self, py_node, class_name="RebuiltNode"):
        from mpynode._common.io import py_export

        return py_export.generate_node_script(py_node, class_name=class_name)

    def test_generated_source_is_valid_python(self):
        from mpynode import MPyNode

        n = MPyNode.create(name="srcOk#")
        n.add_input_attr("inFloat", "float")
        n.add_output_attr("outFloat", "float")
        n.set_compute_expression("self.outFloat = self.inFloat")
        src = self._gen(n)
        ast.parse(src)                    # raises SyntaxError if codegen is malformed
        self.assertIn("class RebuiltNode(MPyNode):", src)
        self.assertIn("def build(cls", src)
        self.assertNotIn("def ls(", src)  # ls is inherited, not emitted
        self.assertIn("from mpynode import MPyNode", src)

    def test_basic_roundtrip(self):
        from mpynode import MPyNode

        n = MPyNode.create(name="basic#")
        n.add_input_attr("inFloat", "float")
        n.add_output_attr("outFloat", "float")
        n.set_compute_expression("self.outFloat = self.inFloat")

        cls     = _build_cls(self._gen(n), "RebuiltNode")
        rebuilt = cls.build(name="rebuiltBasic#")

        self.assertIsInstance(rebuilt, cls)
        self.assertEqual(rebuilt.get_input_attr_map(), n.get_input_attr_map())
        self.assertEqual(rebuilt.get_output_attr_map(), n.get_output_attr_map())
        self.assertEqual(
            rebuilt.get_compute_expression(), n.get_compute_expression()
        )

    def test_enum_array_limits_color_roundtrip(self):
        from mpynode import MPyNode

        n = MPyNode.create(name="rich#")
        n.add_input_attr("mode", "enum", enum_names=["off", "on", "auto"])
        n.add_input_attr("points", "vector", is_array=True)
        n.add_input_attr(
            "amp", "float", min_value=0.0, max_value=1.0, default_value=0.5
        )
        n.set_input_attr_color("amp", "#ff0000")
        n.add_output_attr("result", "vector")

        cls     = _build_cls(self._gen(n), "RebuiltNode")
        rebuilt = cls.build(name="rebuiltRich#")

        # Full attr-map equality proves type/array/enum/limits/color all survived.
        self.assertEqual(rebuilt.get_input_attr_map(), n.get_input_attr_map())
        self.assertEqual(rebuilt.get_output_attr_map(), n.get_output_attr_map())

    def test_sparse_roundtrips(self):
        # A sparse array must survive the .py round trip. The dense default
        # carries no marker, so the deviation is what the exporter must record.
        from mpynode import MPyNode

        n = MPyNode.create(name="sparse#")
        n.add_input_attr("dense", "float", is_array=True)  # default dense
        n.add_input_attr("packed", "float", is_array=True, sparse=True)

        cls     = _build_cls(self._gen(n, "RebuiltSparse"), "RebuiltSparse")
        rebuilt = cls.build(name="rebuiltSparse#")

        self.assertEqual(rebuilt.get_input_attr_map(), n.get_input_attr_map())
        self.assertTrue(
            rebuilt.get_input_attr_map()["packed"]["sparse"]
        )
        self.assertFalse(
            rebuilt.get_input_attr_map()["dense"].get("sparse", False)
        )

    def test_init_expression_roundtrip(self):
        from mpynode import MPyNode

        n = MPyNode.create(name="withInit#")
        n.add_output_attr("out", "float")
        n.set_init_expression("import numpy as np\nK = 3")
        n.set_compute_expression("self.out = float(K)")

        cls     = _build_cls(self._gen(n), "RebuiltNode")
        rebuilt = cls.build(name="rebuiltInit#")
        self.assertEqual(rebuilt.get_init_expression(), n.get_init_expression())
        self.assertEqual(
            rebuilt.get_compute_expression(), n.get_compute_expression()
        )

    def test_init_and_compute_multiline_are_triplequoted_blocks(self):
        # Both Init and Compute must emit as readable multi-line triple-quoted
        # blocks (real line breaks), never a repr() one-liner.
        from mpynode import MPyNode

        n = MPyNode.create(name="multiline#")
        n.add_output_attr("out", "float")
        n.set_init_expression("import numpy as np\nimport math\nK = 3")
        n.set_compute_expression("x = K\ny = x * 2\nself.out = float(y)")
        src = self._gen(n)
        self.assertIn('set_init_expression("""', src)
        self.assertIn('set_compute_expression("""', src)
        # NOT a repr single-quoted one-liner:
        self.assertNotIn("set_init_expression('", src)
        self.assertIn("\nimport math\n", src)  # init really spans lines

        cls = _build_cls(src, "RebuiltNode")
        rb  = cls.build(name="rbMulti#")
        self.assertEqual(rb.get_init_expression(), n.get_init_expression())
        self.assertEqual(rb.get_compute_expression(), n.get_compute_expression())

    def test_init_with_backslash_is_readable_block_and_roundtrips(self):
        # The reported bug: an Init expr with a backslash (e.g. a regex) was
        # emitted via repr() as one long line. It must be a readable (raw)
        # multi-line block AND round-trip the backslash exactly.
        from mpynode import MPyNode

        n = MPyNode.create(name="bsInit#")
        n.add_output_attr("out", "float")
        init = 'import re\nPAT = re.compile(r"\\d+")\nK = 1'  # stored: real \n + \d
        n.set_init_expression(init)
        n.set_compute_expression("self.out = float(K)")
        src = self._gen(n)
        self.assertIn('set_init_expression(r"""', src)  # raw block, not repr
        self.assertNotIn("set_init_expression('", src)
        self.assertIn("\nPAT = re.compile", src)        # spans lines

        cls = _build_cls(src, "RebuiltNode")
        rb  = cls.build(name="rbBs#")
        self.assertEqual(rb.get_init_expression(), n.get_init_expression())

    def test_viewport_expression_roundtrips(self):
        from mpynode import MPyFile

        f = MPyFile.create(name="withPipe#")
        f.add_output_attr("out", "float")
        f.set_viewport_expression("a = 1\nb = 2\nresult = a + b")
        src = self._gen(f, class_name="RebuiltFile")
        self.assertIn("from mpynode import MPyFile", src)
        self.assertIn('set_viewport_expression("""', src)

        cls = _build_cls(src, "RebuiltFile")
        rb  = cls.build(name="rbPipe#")
        self.assertEqual(
            rb.get_viewport_expression(), f.get_viewport_expression()
        )

    def test_no_viewport_call_for_node_without_viewport(self):
        # Base mPyNode has no set_viewport_expression -- emitting one would
        # AttributeError on rebuild, so it must be omitted.
        from mpynode import MPyNode

        n = MPyNode.create(name="noPipe#")
        n.add_output_attr("out", "float")
        n.set_compute_expression("self.out = 1.0")
        self.assertNotIn("set_viewport_expression", self._gen(n))

    def test_osl_expression_roundtrips(self):
        # The OSL tier is authored in the UI and .mpn already round-trips it
        # (osl_source), so the bake must carry it too -- omitting it silently
        # dropped the whole tier.
        from mpynode import MPyFile

        f = MPyFile.create(name="withOsl#")
        f.add_output_attr("out", "float")
        f.set_osl_expression("shader gol(output color c = 0) { c = 1; }")
        src = self._gen(f, class_name="RebuiltOsl")
        self.assertIn('set_osl_expression("""', src)

        cls = _build_cls(src, "RebuiltOsl")
        rb  = cls.build(name="rbOsl#")
        self.assertEqual(rb.get_osl_expression(), f.get_osl_expression())

    def test_no_osl_call_for_node_without_osl(self):
        # Same opt-in rule as viewport: base mPyNode has no
        # set_osl_expression, so emitting one would AttributeError on rebuild.
        from mpynode import MPyNode

        n = MPyNode.create(name="noOsl#")
        n.add_output_attr("out", "float")
        n.set_compute_expression("self.out = 1.0")
        self.assertNotIn("set_osl_expression", self._gen(n))

    def test_persistent_var_declared_but_data_not_embedded(self):
        import numpy as np

        from mpynode import MPyNode

        n = MPyNode.create(name="withVar#")
        n.add_output_attr("out", "float")
        n.add_variable("payload", np.arange(1000) + 314159, persistent=True)

        src = self._gen(n)
        # Declared...
        self.assertIn("payload",         src)
        self.assertIn("add_variable",    src)
        self.assertIn("persistent=True", src)
        # ...but the DATA is not packed (no pickle/base64, no array contents).
        self.assertNotIn("314159", src)
        self.assertNotIn("base64", src.lower())
        self.assertNotIn("array(", src)

        cls     = _build_cls(src, "RebuiltNode")
        rebuilt = cls.build(name="rebuiltVar#")
        self.assertIn("payload", rebuilt.get_variable_names())     # re-declared
        self.assertTrue(rebuilt.is_variable_persistent("payload"))
        self.assertIsNone(rebuilt.get_variables().get("payload"))  # data NOT carried

    def test_ls_inherited_from_root_wrapper(self):
        from mpynode import MPyNode

        n = MPyNode.create(name="forLs#")
        n.add_output_attr("out", "float")
        src = self._gen(n, class_name="RebuiltNode")
        # ls is no longer emitted -- it is inherited from the root wrapper.
        self.assertNotIn("def ls(", src)
        cls = _build_cls(src, "RebuiltNode")
        self.assertTrue(hasattr(cls, "ls"))
        made = cls.build(name="lsInstance#")
        # The rebuilt node is discoverable via the root wrapper's scoped ls()
        # (base MPyNode.ls() returns every node of the native type).
        names = [x.get_name() for x in MPyNode.ls()]
        self.assertIn(made.get_name(), names)

    def test_deformer_uses_create_on_with_mesh_param(self):
        from mpynode import MPyDeformer

        mesh = mc.polySphere(name="defTarget#")[0]
        d    = MPyDeformer.create_on(mesh)
        d.add_output_attr("out", "float")

        src = self._gen(d, class_name="MyDeformer")
        ast.parse(src)
        self.assertIn("class MyDeformer(MPyDeformer):", src)
        self.assertIn("from mpynode import MPyDeformer", src)
        self.assertIn("def build(cls, mesh", src)
        self.assertIn("create_on(mesh", src)

        # And it actually rebuilds when given a mesh.
        mesh2   = mc.polySphere(name="defTarget2#")[0]
        cls     = _build_cls(src, "MyDeformer")
        rebuilt = cls.build(mesh2, name="rebuiltDef#")
        self.assertIsInstance(rebuilt, cls)
        self.assertEqual(rebuilt.get_output_attr_map(), d.get_output_attr_map())

    def test_written_file_imports_and_rebuilds(self):
        # The export handler writes the script to a .py FILE -- prove that file
        # imports as a real module and rebuilds the node (covers I/O/encoding).
        import importlib.util
        import os
        import tempfile

        from mpynode import MPyNode

        n = MPyNode.create(name="fileExport#")
        n.add_input_attr("inFloat", "float")
        n.add_output_attr("outFloat", "float")
        n.set_compute_expression("self.outFloat = self.inFloat")

        src  = self._gen(n, class_name="FromFile")
        path = os.path.join(tempfile.mkdtemp(), "exported_node.py")
        # Explicit UTF-8: the generated source carries non-ASCII (U+25B8),
        # and Windows defaults text mode to cp1252, which cannot encode it.
        # Python reads .py as UTF-8 (PEP 263), so this is also what exec wants.
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)

        spec = importlib.util.spec_from_file_location("exported_node", path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rebuilt = mod.FromFile.build(name="fromFile#")
        self.assertIsInstance(rebuilt, mod.FromFile)
        self.assertEqual(rebuilt.get_input_attr_map(), n.get_input_attr_map())
        self.assertEqual(
            rebuilt.get_compute_expression(), n.get_compute_expression()
        )

    def test_class_name_defaults_to_valid_identifier(self):
        from mpynode._common.io import py_export

        from mpynode import MPyNode

        n = MPyNode.create(name="weird#")
        # rename to something that is NOT a valid identifier
        n.set_name("1weird-name")
        src = py_export.generate_node_script(n)  # no class_name -> derive it
        ast.parse(src)  # must still be valid Python
        # find the generated class name from the source
        tree      = ast.parse(src)
        classdefs = [c for c in ast.walk(tree) if isinstance(c, ast.ClassDef)]
        self.assertEqual(len(classdefs), 1)
        self.assertTrue(classdefs[0].name.isidentifier())

    def test_docstring_only_uses_single_triple_quote(self):
        # An expression embedding a """ docstring (but no ''') can't use a
        # """ block -> switch to a readable '''...''' block (NOT the verbose
        # accumulator), round-tripping exactly.
        from mpynode import MPyNode

        n = MPyNode.create(name="docstr#")
        n.add_output_attr("out", "float")
        init = (
            "import math\n"
            "def helper():\n"
            '    """Return a constant."""\n'
            "    return 3\n"
            "K = helper()"
        )
        n.set_init_expression(init)
        n.set_compute_expression("self.out = float(K)")

        src = self._gen(n)
        self.assertIn("set_init_expression('''", src)      # switched to '''
        self.assertNotIn("set_init_expression(exp)", src)  # not accumulator
        self.assertNotIn('set_init_expression("""', src)   # not colliding """

        cls = _build_cls(src, "RebuiltNode")
        rb  = cls.build(name="rbDoc#")
        self.assertEqual(rb.get_init_expression(), n.get_init_expression())
        self.assertEqual(
            rb.get_compute_expression(), n.get_compute_expression()
        )

    def test_trailing_double_quote_uses_single_triple_quote(self):
        # Ends with a " -> a """ block would merge delimiters; switch to a
        # '''...''' block (not the accumulator) and round-trip.
        from mpynode import MPyNode

        n = MPyNode.create(name="trailq#")
        n.add_output_attr("out", "float")
        compute = (
            'label = "ready"\n'
            'self.out = 1.0 if label == "ready" else 0.0\n'
            'msg = "done"'
        )
        n.set_compute_expression(compute)

        src = self._gen(n)
        self.assertIn("set_compute_expression('''", src)
        self.assertNotIn("set_compute_expression(exp)", src)

        cls = _build_cls(src, "RebuiltNode")
        rb  = cls.build(name="rbTrailq#")
        self.assertEqual(
            rb.get_compute_expression(), n.get_compute_expression()
        )

    def test_single_triple_quote_only_keeps_double_triple_quote(self):
        # Embeds a ''' (but no """) -> the default """ block still works, so
        # keep it (double is preferred); round-trip exactly.
        from mpynode import MPyNode

        n = MPyNode.create(name="tsq#")
        n.add_output_attr("out", "float")
        init = "doc = '''a triple-single-quoted\nblock'''\nK = 1"
        n.set_init_expression(init)
        n.set_compute_expression("self.out = float(K)")

        src = self._gen(n)
        self.assertIn('set_init_expression("""', src)        # kept default """
        self.assertNotIn("set_init_expression(exp)", src)

        cls = _build_cls(src, "RebuiltNode")
        rb  = cls.build(name="rbTsq#")
        self.assertEqual(rb.get_init_expression(), n.get_init_expression())

    def test_trailing_single_quote_keeps_double_triple_quote(self):
        # Ends with ' -> a """ block is fine (' doesn't collide with "); keep
        # the default """ block and round-trip.
        from mpynode import MPyNode

        n = MPyNode.create(name="trails#")
        n.add_output_attr("out", "float")
        compute = "self.out = 1.0\nlabel = 'done'"
        n.set_compute_expression(compute)
        src = self._gen(n)
        self.assertIn('set_compute_expression("""', src)
        cls = _build_cls(src, "RebuiltNode")
        rb  = cls.build(name="rbTrails#")
        self.assertEqual(
            rb.get_compute_expression(), n.get_compute_expression()
        )

    def test_both_triple_quotes_use_accumulator(self):
        # Embeds BOTH """ and ''' -> neither triple-quote delimiter is safe ->
        # fall back to the readable line-by-line accumulator; round-trip.
        from mpynode import MPyNode

        n = MPyNode.create(name="both#")
        n.add_output_attr("out", "float")
        init = 'a = """double doc"""\nb = \'\'\'single doc\'\'\'\nK = 1'
        n.set_init_expression(init)
        n.set_compute_expression("self.out = float(K)")

        src = self._gen(n)
        self.assertIn("set_init_expression(exp)", src)       # accumulator
        self.assertIn("exp = ", src)
        self.assertIn("exp += ", src)

        cls = _build_cls(src, "RebuiltNode")
        rb  = cls.build(name="rbBoth#")
        self.assertEqual(rb.get_init_expression(), n.get_init_expression())

    def test_docstring_with_backslash_uses_raw_single_triple_quote(self):
        # A """ docstring (switch to ''') AND a backslash (raw prefix) ->
        # r'''...''' block, round-tripping the backslash + docstring exactly.
        from mpynode import MPyNode

        n = MPyNode.create(name="rawdoc#")
        n.add_output_attr("out", "float")
        init = 'import re\nPAT = re.compile(r"\\d+")\nx = """doc"""\nK = 1'
        n.set_init_expression(init)

        src = self._gen(n)
        self.assertIn("set_init_expression(r'''", src)       # raw + single triple
        cls = _build_cls(src, "RebuiltNode")
        rb  = cls.build(name="rbRawDoc#")
        self.assertEqual(rb.get_init_expression(), n.get_init_expression())

    def test_viewport_docstring_uses_single_triple_quote_and_roundtrips(self):
        from mpynode import MPyFile

        f = MPyFile.create(name="pipeDoc#")
        f.add_output_attr("out", "float")
        pipe = (
            "def post():\n"
            '    """Post-process the result."""\n'
            "    return 1\n"
            "result = post()"
        )
        f.set_viewport_expression(pipe)

        src = self._gen(f, class_name="RebuiltFile")
        self.assertIn("set_viewport_expression('''", src)

        cls = _build_cls(src, "RebuiltFile")
        rb  = cls.build(name="rbPipeDoc#")
        self.assertEqual(
            rb.get_viewport_expression(), f.get_viewport_expression()
        )

    def test_normal_multiline_still_uses_triplequoted_block(self):
        # Regression guard: ordinary multi-line code (no embedded triple-quote,
        # no trailing quote/backslash) must STAY a default """ block, NOT switch
        # to ''' or the accumulator.
        from mpynode import MPyNode

        n = MPyNode.create(name="normal#")
        n.add_output_attr("out", "float")
        n.set_compute_expression("x = 1\ny = x + 1\nself.out = float(y)")
        src = self._gen(n)
        self.assertIn('set_compute_expression("""', src)
        self.assertNotIn("exp = ", src)
        self.assertNotIn("exp += ", src)

    def test_carriage_return_expression_roundtrips(self):
        # A CR in a triple-quoted literal is silently rewritten to "\n" by
        # universal newlines, corrupting the round-trip. CR-bearing expressions
        # must route through the accumulator (repr escapes \r) instead.
        from mpynode import MPyNode

        for label, expr in [
            ("crlf", "import os\r\nos.getcwd()\r\n"),
            ("lone_cr", "a\rb\rc"),
            ("trailing_cr", "x\r"),
        ]:
            with self.subTest(label=label):
                n = MPyNode.create(name="cr_%s#" % label)
                n.add_output_attr("out", "float")
                n.set_init_expression(expr)
                stored = n.get_init_expression()
                self.assertEqual(stored, expr)  # Maya keeps the CR verbatim
                src = self._gen(n, class_name="Cr")
                self.assertIn("set_init_expression(exp)", src)  # accumulator
                cls = _build_cls(src, "Cr")
                rb  = cls.build(name="rbcr_%s#" % label)
                self.assertEqual(rb.get_init_expression(), stored)

    def test_methods_are_baked_not_emitted_as_source(self):
        # One-way bake: a @maya_command Methods tab is emitted as REAL Python (a
        # class member, decorator intact), NOT re-stored via
        # ``set_methods_source`` -- the editable blob is gone (use .mpn).
        from mpynode import MPyLocator

        src_methods = (
            "from mpynode._common.methods.maya_command import maya_command\n"
            "\n"
            "@maya_command(name='setMeshRegion')\n"
            "def set_region(self, indices=None):\n"
            "    return indices\n"
        )
        loc = MPyLocator.create(name="mLoc#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltLoc")
        ast.parse(gen)
        self.assertIn("from mpynode import MPyLocator", gen)
        self.assertNotIn("set_methods_source", gen)  # one-way: no blob
        self.assertIn("@maya_command(name='setMeshRegion')", gen)
        self.assertIn("def set_region(self, indices=None):", gen)

        cls = _build_cls(gen, "RebuiltLoc")
        rb  = cls.build(name="rbLoc#")
        self.assertEqual(rb.set_region(indices=[1, 2, 3]), [1, 2, 3])

    def test_ambient_decorators_are_imported_by_the_bake(self):
        # The Methods tab injects maya_command / maya_demo / maya_test into the
        # exec namespace, so a real template's source does NOT import them --
        # the bake has to. Note this source deliberately has NO import line.
        #
        # compile() does NOT catch a missing one: the decorator name resolves
        # only when the class body EXECUTES. That is why every shipped template
        # baked a .py that raised NameError on import while the suite stayed
        # green -- so this test execs (via _build_cls) rather than just parsing.
        from mpynode import MPyLocator

        src_methods = (
            "@maya_command(name='doThing')\n"
            "def do_thing(self):\n"
            "    return 1\n"
            "\n"
            "@maya_demo(label='Demo')\n"
            "def demo_thing(self):\n"
            "    return 2\n"
            "\n"
            "@maya_test(label='Test')\n"
            "def test_thing(self):\n"
            "    return 3\n"
        )
        loc = MPyLocator.create(name="mAmb#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltAmb")
        for dec in ("maya_command", "maya_demo", "maya_test"):
            self.assertIn(
                "from mpynode._common.methods.maya_command import %s" % dec,
                gen,
                "bake must supply the ambient %s import" % dec,
            )
        cls = _build_cls(gen, "RebuiltAmb")   # execs: NameError if any is missing
        rb  = cls.build(name="rbAmb#")
        self.assertEqual(rb.test_thing(), 3)

    def test_methods_emitted_as_real_members(self):
        # The "broader API": each @maya_command becomes a real method on the
        # generated class, callable directly (outside the input/output paradigm).
        from mpynode import MPyLocator

        src_methods = (
            "from mpynode._common.methods.maya_command import maya_command\n"
            "\n"
            "@maya_command(name='setMeshRegion')\n"
            "def set_region(self, indices=None):\n"
            "    return indices\n"
        )
        loc = MPyLocator.create(name="mLoc2#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltLoc2")
        # the marker import shim + the real def member
        self.assertIn(
            "from mpynode._common.methods.maya_command import maya_command", gen)
        self.assertIn("def set_region(self, indices=None):", gen)
        self.assertIn("@maya_command(name='setMeshRegion')", gen)

        cls = _build_cls(gen, "RebuiltLoc2")
        rb  = cls.build(name="rbLoc2#")
        # callable directly on the instance
        self.assertTrue(callable(getattr(rb, "set_region", None)))
        self.assertEqual(rb.set_region(indices=[1, 2, 3]), [1, 2, 3])

    def test_no_methods_no_command_import(self):
        # A node without a Methods tab must not gain the maya_command import or a
        # set_methods_source call.
        from mpynode import MPyNode

        n = MPyNode.create(name="noMeth#")
        n.add_output_attr("out", "float")
        n.set_compute_expression("self.out = 1.0")
        gen = self._gen(n)
        self.assertNotIn("set_methods_source", gen)
        self.assertNotIn("maya_command", gen)

    def test_methods_top_level_imports_are_hoisted_to_module(self):
        # Top-level imports used by a @maya_command body must land at MODULE
        # scope of the generated .py, not just inside set_methods_source(...),
        # or calling the real-member command on the rebuilt instance NameErrors.
        from mpynode import MPyLocator

        src_methods = (
            "import maya.cmds as cmds\n"
            "from mpynode._common.methods.maya_command import maya_command\n"
            "\n"
            "@maya_command\n"
            "def list_transforms(self):\n"
            "    return cmds.ls(type='transform') or []\n"
        )
        loc = MPyLocator.create(name="mLocImp#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltLocImp")
        # MODULE-LEVEL import: the line must appear at column 0 anywhere in the
        # generated source.
        self.assertIn("\nimport maya.cmds as cmds\n", gen)
        cls = _build_cls(gen, "RebuiltLocImp")
        rb  = cls.build(name="rbLocImp#")
        # Calling the real-member command must NOT NameError on `cmds`.
        result = rb.list_transforms()
        self.assertIsInstance(result, list)

    def test_methods_marker_import_is_not_duplicated(self):
        # The marker import is emitted by py_export itself; if the Methods
        # source ALSO has it, py_export must NOT hoist a second copy
        # (_top_level_import_lines skips the marker).
        from mpynode import MPyLocator

        src_methods = (
            "from mpynode._common.methods.maya_command import maya_command\n"
            "\n"
            "@maya_command\n"
            "def noop(self):\n"
            "    return 0\n"
        )
        loc = MPyLocator.create(name="mLocMarkerImp#")
        loc.set_methods_source(src_methods)
        gen    = self._gen(loc, class_name="RebuiltMarkerImp")
        marker = "from mpynode._common.methods.maya_command import maya_command"
        # Real top-level import lines start at column 0, so require a newline
        # either side of the match. Exactly one such line must exist.
        toplevel = gen.count("\n" + marker + "\n")
        self.assertEqual(toplevel, 1, gen)

    def test_command_without_authored_import_still_bakes_marker(self):
        # Ambient decorators: a @maya_command method authored WITHOUT the marker
        # import (the runtime pre-injects it) must STILL bake to a valid
        # standalone .py -- py_export re-synthesizes the import from
        # detect_commands, so the decorator resolves on import.
        from mpynode import MPyLocator

        src_methods = (
            "@maya_command(name='setMeshRegion')\n"
            "def set_region(self, indices=None):\n"
            "    return indices\n"
        )
        loc = MPyLocator.create(name="mLocAmbient#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltAmbient")
        ast.parse(gen)
        # The marker import is emitted even though the source omitted it.
        self.assertIn(
            "from mpynode._common.methods.maya_command import maya_command", gen)
        self.assertIn("@maya_command(name='setMeshRegion')", gen)

        cls = _build_cls(gen, "RebuiltAmbient")
        rb  = cls.build(name="rbAmbient#")
        self.assertEqual(rb.set_region(indices=[1, 2, 3]), [1, 2, 3])

    def test_plain_helper_def_is_emitted_alongside_command(self):
        # F10: a @maya_command def that calls a sibling plain ``def`` from
        # the Methods source must work after rebuild -- the plain helper has
        # to be emitted as a real class member too, not silently dropped (the
        # old loop only emitted @maya_command-decorated defs).
        from mpynode import MPyLocator

        src_methods = (
            "from mpynode._common.methods.maya_command import maya_command\n"
            "\n"
            "def _double(self, n):\n"
            "    return n * 2\n"
            "\n"
            "@maya_command\n"
            "def scale(self, n=0):\n"
            "    return self._double(n)\n"
        )
        loc = MPyLocator.create(name="mLocHelper#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltLocHelper")
        self.assertIn("def _double(self, n):", gen)
        self.assertIn("def scale(self, n=0):", gen)
        cls = _build_cls(gen, "RebuiltLocHelper")
        rb  = cls.build(name="rbLocHelper#")
        self.assertEqual(rb.scale(n=3), 6)

    def test_reserved_name_helper_is_skipped_with_warning_comment(self):
        # F11: a Methods def named ``build`` would shadow the generated
        # @classmethod build(); it must be skipped with a # WARNING comment
        # rather than silently emitted (which would crash the rebuild).
        from mpynode import MPyLocator

        src_methods = (
            "from mpynode._common.methods.maya_command import maya_command\n"
            "\n"
            "@maya_command\n"
            "def build(self):\n"
            "    return 'oops'\n"
            "\n"
            "@maya_command\n"
            "def normal(self):\n"
            "    return 1\n"
        )
        loc = MPyLocator.create(name="mLocReserved#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltLocReserved")
        # Class-member defs are at four-space indent; the same text inside the
        # set_methods_source(...) block is flush-left. A shadow member would
        # also be at "    def build(", so the count must be exactly 1.
        self.assertEqual(gen.count("    def build("), 1)
        self.assertIn("# WARNING", gen)
        self.assertIn("'build'", gen)  # warning names the offender
        cls = _build_cls(gen, "RebuiltLocReserved")
        rb  = cls.build(name="rbLocReserved#")
        self.assertEqual(rb.normal(), 1)

    def test_base_wrapper_method_shadow_is_skipped_with_warning_comment(self):
        # A Methods def whose name also exists on the ROOT WRAPPER lands in
        # ``class X(MPyBlendShape)`` and overrides the very method its body
        # forwards to -- measured RecursionError before this guard. Skipping it
        # leaves the inherited implementation, which is what the body meant.
        from mpynode import MPyBlendShape

        base = mc.polySphere(r=1.0, sx=6, sy=6, name="bsShadowBase#")[0]
        src_methods = (
            "from mpynode._common.methods.maya_command import maya_command\n"
            "\n"
            "@maya_command\n"
            "def load_target(self, path, name=''):\n"
            "    return self.load_target(path, name=name or None)\n"
            "\n"
            "@maya_command\n"
            "def untaken(self):\n"
            "    return 7\n"
        )
        bs = MPyBlendShape.create(mesh=base, name="mBsShadow#")
        bs.set_methods_source(src_methods)
        gen = self._gen(bs, class_name="RebuiltBsShadow")
        # No class-member override -- flush-left hits are the payload string.
        self.assertEqual(gen.count("    def load_target("), 0)
        self.assertIn("# WARNING", gen)
        self.assertIn("'load_target'", gen)              # warning names the offender
        self.assertIn("MPyBlendShape.load_target", gen)  # ...and what it hid
        # A non-colliding sibling still bakes normally.
        self.assertIn("    def untaken(self):", gen)
        cls = _build_cls(gen, "RebuiltBsShadow")
        self.assertIs(cls.load_target, MPyBlendShape.load_target)

    def test_base_wrapper_property_shadow_is_skipped(self):
        # The SILENT variant: a def shadowing a wrapper @property raises
        # nothing -- reading self.X just yields a bound method and the property
        # body never runs. The guard must catch descriptors too, not only
        # functions, and must probe the CLASS (hasattr on an INSTANCE raises
        # out of a property that reads an unconnected plug).
        from mpynode import MPyBlendShape

        base = mc.polySphere(r=1.0, sx=6, sy=6, name="bsPropBase#")[0]
        src_methods = (
            "def target_count(self):\n"
            "    return -1\n"
        )
        bs = MPyBlendShape.create(mesh=base, name="mBsProp#")
        bs.set_methods_source(src_methods)
        gen = self._gen(bs, class_name="RebuiltBsProp")
        self.assertEqual(gen.count("    def target_count("), 0)
        self.assertIn("'target_count'", gen)
        cls = _build_cls(gen, "RebuiltBsProp")
        # Still the inherited PROPERTY, not a function.
        self.assertIsInstance(
            inspect.getattr_static(cls, "target_count"), property)

    def test_setup_and_demo_are_exempt_from_the_base_shadow_guard(self):
        # The two authoring hooks are resolved by name out of the Methods
        # namespace, never off the wrapper, so they must keep baking even
        # though the guard's predicate would otherwise be free to grow onto
        # them. ``demo`` appears in 43/43 shipped template sources.
        from mpynode import MPyBlendShape

        base = mc.polySphere(r=1.0, sx=6, sy=6, name="bsHookBase#")[0]
        src_methods = (
            "def setup(self, selection=None):\n"
            "    return 'ran-setup'\n"
            "\n"
            "def demo(self):\n"
            "    return 'ran-demo'\n"
        )
        bs = MPyBlendShape.create(mesh=base, name="mBsHook#")
        bs.set_methods_source(src_methods)
        gen = self._gen(bs, class_name="RebuiltBsHook")
        self.assertIn("    def setup(self, selection=None):", gen)
        self.assertIn("    def demo(self):", gen)
        cls = _build_cls(gen, "RebuiltBsHook")
        self.assertEqual(cls("mBsHook1").demo(), "ran-demo")

    def test_dunder_defs_are_exempt_from_the_base_shadow_guard(self):
        # Every dunder resolves via ``object``, so an unguarded predicate would
        # silently delete any __repr__ / __eq__ an author writes.
        from mpynode import MPyLocator

        src_methods = (
            "def __repr__(self):\n"
            "    return 'BakedLoc()'\n"
        )
        loc = MPyLocator.create(name="mLocDunder#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltLocDunder")
        self.assertIn("    def __repr__(self):", gen)

    def test_duplicate_helper_defs_are_deduped_with_warning(self):
        # F11: two top-level defs with the same name -- the SECOND must be
        # skipped with a # WARNING comment, and only one def member emitted.
        from mpynode import MPyLocator

        src_methods = (
            "from mpynode._common.methods.maya_command import maya_command\n"
            "\n"
            "def helper(self):\n"
            "    return 1\n"
            "\n"
            "def helper(self):\n"
            "    return 2\n"
            "\n"
            "@maya_command\n"
            "def caller(self):\n"
            "    return self.helper()\n"
        )
        loc = MPyLocator.create(name="mLocDup#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltLocDup")
        # Count CLASS-MEMBER def lines only (four-space indent); flush-left
        # occurrences are inside the set_methods_source(...) string payload.
        self.assertEqual(gen.count("    def helper(self):"), 1)
        self.assertIn("# WARNING", gen)
        self.assertIn("'helper'", gen)
        cls = _build_cls(gen, "RebuiltLocDup")
        rb  = cls.build(name="rbLocDup#")
        # FIRST def wins (1) -- the dedupe must drop the LATER duplicate.
        self.assertEqual(rb.caller(), 1)

    def test_free_function_hoisted_to_module_scope(self):
        # One-way bake: a plain helper ``def`` (no self/cls) is NOT a method, so
        # it hoists to MODULE scope. An instance method that calls it must still
        # resolve after rebuild.
        from mpynode import MPyLocator

        src_methods = (
            "def _area(r):\n"
            "    return 3 * r * r\n"
            "\n"
            "def circle_area(self, r=0):\n"
            "    return _area(r)\n"
        )
        loc = MPyLocator.create(name="mLocFreeFn#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltFreeFn")
        # Hoisted to module scope (column 0), NOT emitted as a class member.
        self.assertIn("\ndef _area(r):", gen)
        self.assertNotIn("    def _area(r):", gen)
        cls = _build_cls(gen, "RebuiltFreeFn")
        rb  = cls.build(name="rbFreeFn#")
        self.assertEqual(rb.circle_area(r=2), 12)

    def test_module_level_constant_is_hoisted(self):
        # One-way bake: a top-level constant in the Methods source must be hoisted
        # to MODULE scope, or a baked method that references it NameErrors. (Only
        # imports were hoisted before -- a real correctness gap.)
        from mpynode import MPyLocator

        src_methods = (
            "from mpynode._common.methods.maya_command import maya_command\n"
            "\n"
            "PREFIX = 'rgn_'\n"
            "\n"
            "@maya_command\n"
            "def make_id(self, i=0):\n"
            "    return PREFIX + str(i)\n"
        )
        loc = MPyLocator.create(name="mLocConst#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltConst")
        self.assertIn("\nPREFIX = 'rgn_'", gen)  # module scope (column 0)
        cls = _build_cls(gen, "RebuiltConst")
        rb  = cls.build(name="rbConst#")
        self.assertEqual(rb.make_id(i=2), "rgn_2")

    def test_staticmethod_stays_on_class_not_module(self):
        # A @staticmethod has no self/cls first param but is still a METHOD -- it
        # must stay in the class body, NOT be misrouted to module scope.
        from mpynode import MPyLocator

        src_methods = (
            "def util(self, n=0):\n"
            "    return self.helper(n)\n"
            "\n"
            "@staticmethod\n"
            "def helper(n):\n"
            "    return n + 1\n"
        )
        loc = MPyLocator.create(name="mLocStatic#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltStatic")
        self.assertIn("    @staticmethod", gen)    # kept as a class member
        self.assertIn("    def helper(n):", gen)   # indented (class scope)
        self.assertNotIn("\ndef helper(n):", gen)  # NOT hoisted to module scope
        cls = _build_cls(gen, "RebuiltStatic")
        rb  = cls.build(name="rbStatic#")
        self.assertEqual(rb.util(n=4), 5)

    def test_the_one_way_bake_is_documented_but_not_in_the_file(self):
        # The bake IS a one-way trip and that has to be stated somewhere --
        # but not as 16 lines above the user's code on every node. The text is
        # BAKE_CONTRACT, rendered by the Identity tab.
        from mpynode import MPyNode
        from mpynode._common.io.py_export import BAKE_CONTRACT

        for phrase in ("ONE-WAY", ".mpn"):
            self.assertIn(phrase, BAKE_CONTRACT)
        n = MPyNode.create(name="hdr#")
        n.add_output_attr("out", "float")
        gen = self._gen(n)
        self.assertNotIn("Bake Node to .py File", gen)
        self.assertNotIn("ONE-WAY", gen)

    def test_pathological_strings_roundtrip(self):
        # Real-execution oracle: each string is pathological for triple-quoting.
        # Whichever emission strategy is chosen, it MUST round-trip
        # byte-for-byte against what Maya STORED.
        from mpynode import MPyNode

        cases = [
            'a = """doc"""',                       # """ only -> ''' block
            'x = 1\ny = """\nmulti\n"""\nz = 2',   # """ only, multi-line
            'q = "ends with a quote"',             # trailing " -> ''' block
            "x = 1\\",                             # trailing backslash -> accumulator
            'a = """x"""\n\nb = 1\n',              # """ + blank line + trailing \n
            'x = "café ☃"',                        # unicode + trailing "
            "mixed = 'single' and \"double\"",     # both quote KINDS (not triples)
            "a = '''doc'''",                       # ''' only -> """ block
            'a = """d""" + b + \'\'\'e\'\'\'',      # BOTH triples -> accumulator
            "label = 'x'",                         # trailing ' -> """ block
            'import re\np = re.compile(r"\\d+")\nx = """doc"""',  # backslash + """
            "line1\r\nline2\r\n",                  # CRLF -> accumulator
            "a\rb\rc",                             # lone CR -> accumulator
            "ends_with_single'",                   # trailing ' (no triples)
            'has """ and ends with backslash \\',  # """ + trailing \ -> accumulator
        ]
        for i, case in enumerate(cases):
            with self.subTest(case=repr(case)):
                n = MPyNode.create(name="adv%d#" % i)
                n.add_output_attr("out", "float")
                n.set_init_expression(case)
                stored = n.get_init_expression()  # what Maya actually persisted
                src    = self._gen(n, class_name="Adv%d" % i)
                cls    = _build_cls(src, "Adv%d" % i)
                rb     = cls.build(name="rbAdv%d#" % i)
                self.assertEqual(rb.get_init_expression(), stored)


class TestSelfFirstSetupNotDecorated(unittest.TestCase):
    """LOCK (regression guard): a self-first ``def setup(self)`` body (the
    setup-on-existing-node contract) must round-trip through
    ``generate_node_script`` WITHOUT gaining ``@classmethod``.

    This is correct-by-construction today: the def classifier only adds
    ``@classmethod`` when the first param is ``cls``, so a ``def setup(self)``
    never gains the decorator. A name-based guard was rejected in review because
    it would suppress the @classmethod that
    ``test_factory_commands.py::test_cls_first_surfaces_as_classmethod`` asserts
    for a genuine ``def setup(cls)`` factory. This test pins that behavior.
    """

    def setUp(self):
        mc.file(new=True, force=True)

    def test_self_first_setup_not_classmethod(self):
        from mpynode._common.io.py_export import generate_node_script

        from mpynode import MPyNode

        node = MPyNode.create(name="selfSetup#")
        node.set_methods_source(
            "def setup(self, *args, **kwargs):\n    return self\n"
        )
        # The entry point takes the WRAPPER, not a node-name string (matching
        # every call here and in test_factory_commands.py::TestFactoryExport).
        out = generate_node_script(node, class_name="Exp")
        self.assertIn("def setup(self", out)
        self.assertNotRegex(out, r"@classmethod\s+def setup\(self")


class TestDemoHookExport(unittest.TestCase):
    """The reserved ``def demo(self)`` hook (a self-contained showcase-scene
    builder, sibling of ``def setup``) must bake as a real, callable instance
    method so the rebuilt node still lights up the gallery's "Create + Run demo"
    -- and, like ``setup``, it must NOT gain ``@classmethod`` (it is self-first,
    not a ``cls``-first factory)."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _gen(self, py_node, class_name="RebuiltNode"):
        from mpynode._common.io import py_export

        return py_export.generate_node_script(py_node, class_name=class_name)

    def test_demo_hook_bakes_as_callable_real_method(self):
        # One-way bake: the reserved ``def demo(self)`` hook bakes as a real
        # instance method (no editable methods blob). It must be callable on the
        # rebuilt node so the gallery's "Create + Run demo" still works.
        from mpynode import MPyNode

        src_methods = (
            "def demo(self):\n"
            "    from maya import cmds as mc\n"
            "    mc.polyPlane(name=self.get_name() + '_plane')\n"
            "    return self\n"
        )
        n = MPyNode.create(name="withDemo#")
        n.add_output_attr("out", "float")
        n.set_methods_source(src_methods)
        gen = self._gen(n, class_name="RebuiltDemo")
        ast.parse(gen)
        self.assertNotIn("set_methods_source", gen)  # one-way: no blob
        self.assertIn("def demo(self):", gen)

        cls = _build_cls(gen, "RebuiltDemo")
        rb  = cls.build(name="rbDemo#")
        # Baked demo runs without NameError, returns self, and built the scene.
        self.assertIs(rb.demo(), rb)
        self.assertTrue(mc.objExists(rb.get_name() + "_plane"))

    def test_self_first_demo_not_classmethod(self):
        # Mirror of TestSelfFirstSetupNotDecorated for the demo hook: a
        # self-first ``def demo(self)`` must round-trip WITHOUT gaining
        # ``@classmethod`` (the emit gate keys on a ``cls`` first param).
        from mpynode._common.io.py_export import generate_node_script

        from mpynode import MPyNode

        node = MPyNode.create(name="selfDemo#")
        node.set_methods_source(
            "def demo(self, *args, **kwargs):\n    return self\n"
        )
        out = generate_node_script(node, class_name="ExpDemo")
        self.assertIn("def demo(self", out)
        self.assertNotRegex(out, r"@classmethod\s+def demo\(self")

    def test_setup_and_demo_both_survive_shared_namespace(self):
        # A template that ships BOTH hooks plus a shared plain helper: the
        # self-first hooks bake as instance methods, the helper (no self/cls)
        # hoists to MODULE scope, and both hooks must still resolve it.
        from mpynode import MPyLocator

        src_methods = (
            "def _shared_helper(x):\n"
            "    return x * 2\n"
            "\n"
            "def demo(self):\n"
            "    return _shared_helper(1)\n"
            "\n"
            "def setup(self, selection=None, *args, **kwargs):\n"
            "    return _shared_helper(2)\n"
        )
        loc = MPyLocator.create(name="bothHooks#")
        loc.set_methods_source(src_methods)
        gen = self._gen(loc, class_name="RebuiltBoth")
        ast.parse(gen)
        # one-way bake: no editable methods blob; shared helper at module scope.
        self.assertNotIn("set_methods_source", gen)
        self.assertIn("\ndef _shared_helper(x):", gen)
        self.assertNotIn("    def _shared_helper(x):", gen)

        cls = _build_cls(gen, "RebuiltBoth")
        rb  = cls.build(name="rbBoth#")
        # both hooks bake as real instance methods resolving the module helper
        self.assertEqual(rb.demo(), 2)
        self.assertEqual(rb.setup(), 4)


class TestBakeMayaDemo(unittest.TestCase):
    def test_maya_demo_instance_def_is_class_member(self):
        from mpynode._common.io.py_export import _method_kind
        kind, add_cm = _method_kind(
            "@maya_demo\ndef show(self):\n    return 1\n")
        self.assertEqual(kind, "class")
        self.assertFalse(add_cm)

    def test_maya_demo_factory_gets_classmethod(self):
        from mpynode._common.io.py_export import _method_kind
        kind, add_cm = _method_kind(
            "@maya_demo\ndef make(cls):\n    return 1\n")
        self.assertEqual(kind, "class")
        self.assertTrue(add_cm)  # cls-first, no @classmethod -> add one

    def test_maya_demo_paramless_def_forced_to_class(self):
        # Without the marker this would hoist to module scope; the marker forces
        # it into the class body so the decorator resolves on rebuild.
        from mpynode._common.io.py_export import _method_kind
        kind, _ = _method_kind(
            "@maya_demo\ndef weird():\n    return 1\n")
        self.assertEqual(kind, "class")

    def test_plain_free_function_still_module(self):
        from mpynode._common.io.py_export import _method_kind
        kind, _ = _method_kind("def helper(x):\n    return x\n")
        self.assertEqual(kind, "module")

    def test_maya_demo_import_line_skipped_from_hoist(self):
        from mpynode._common.io.py_export import _top_level_import_lines
        src = ("from mpynode._common.methods.maya_command import maya_demo\n"
               "@maya_demo\ndef show(self):\n    return 1\n")
        # The marker import is emitted explicitly by generate_node_script, so it
        # must NOT also appear in the hoisted import list (no duplicate).
        self.assertEqual(_top_level_import_lines(src), [])


class TestRegionMap(unittest.TestCase):
    """``generate_node_script_with_regions`` -- the map the Script tab's API
    view folds and badges against.

    The map is emitted by the SAME pass as the text, so the risk is not that it
    is absent but that it points at the wrong lines. Every test here therefore
    checks a region against the text it claims, never against itself.
    """

    def _gen(self, py_node, class_name="RebuiltRegions"):
        from mpynode._common.io import py_export

        return py_export.generate_node_script_with_regions(
            py_node, class_name=class_name)

    def _node(self, name="regions#"):
        from mpynode import MPyNode

        n = MPyNode.create(name=name)
        n.add_input_attr("inFloat", "float")
        n.add_output_attr("outFloat", "float")
        n.set_compute_expression("self.outFloat = self.inFloat")
        return n

    def _region(self, regions, kind):
        for r in regions:
            if r["kind"] == kind:
                return r
        return None

    def test_delegation_is_byte_identical(self):
        # generate_node_script is now a one-line delegation. If the two ever
        # diverge, every existing bake test is testing a different function
        # from the one the UI reads.
        from mpynode._common.io import py_export

        n = self._node("delegate#")
        src, _regions = self._gen(n)
        self.assertEqual(
            py_export.generate_node_script(n, class_name="RebuiltRegions"),
            src)

    def test_regions_are_in_bounds_and_ordered(self):
        n = self._node("bounds#")
        src, regions = self._gen(n)
        n_lines = len(src.split("\n"))
        self.assertTrue(regions)
        last_end = -1
        for r in regions:
            self.assertLessEqual(0, r["start"], r["kind"])
            self.assertLessEqual(r["start"], r["end"], r["kind"])
            self.assertLess(r["end"], n_lines, r["kind"])
            # Emitted in file order, and never overlapping.
            self.assertGreater(r["start"], last_end, r["kind"])
            last_end = r["end"]

    def test_expression_region_lands_on_its_own_setter(self):
        n = self._node("exprland#")
        n.set_init_expression("import math\nx = math.pi\n")
        src, regions = self._gen(n)
        lines = src.split("\n")
        for kind, setter in (("expr_init", "set_init_expression"),
                             ("expr_compute", "set_compute_expression")):
            r = self._region(regions, kind)
            self.assertIsNotNone(r, kind)
            self.assertIn(setter, lines[r["start"]])
            self.assertEqual(r["owner"], setter)
            self.assertTrue(r["editable"])

    def test_body_col_is_where_the_user_text_starts(self):
        # py_export puts the opening delimiter and the user's FIRST body line on
        # one physical line, so a viewer marking whole lines as generated cannot
        # be honest without this column.
        n = self._node("bodycol#")
        n.set_init_expression("import math\nx = math.pi\n")
        src, regions = self._gen(n)
        lines = src.split("\n")
        r     = self._region(regions, "expr_init")
        head  = lines[r["start"]]
        col   = r["body_col"]
        self.assertTrue(head[:col].endswith('"""'), head[:col])
        self.assertTrue(head[col:].startswith("import math"), head[col:])

    def test_body_col_accounts_for_the_raw_prefix(self):
        # _expr_literal prefixes r"""..."""  whenever the text holds a
        # backslash, which makes the opener FOUR characters, not three.
        # Assuming three silently mis-marked three shipped templates.
        n = self._node("rawpfx#")
        n.set_init_expression("import re\np = re.compile('\\\\d+')\n")
        src, regions = self._gen(n)
        lines = src.split("\n")
        r     = self._region(regions, "expr_init")
        head  = lines[r["start"]]
        self.assertIn('(r"""', head)
        col = r["body_col"]
        self.assertTrue(head[:col].endswith('r"""'), head[:col])
        self.assertTrue(head[col:].startswith("import re"), head[col:])

    def test_single_quote_fallback_still_marks_the_body(self):
        # A body embedding a docstring flips the delimiter to ''' -- Game Of
        # Life's Init really does this.
        n = self._node("sqfall#")
        n.set_init_expression('def f():\n    """doc"""\n    return 1\n')
        src, regions = self._gen(n)
        lines = src.split("\n")
        r     = self._region(regions, "expr_init")
        head  = lines[r["start"]]
        self.assertIn("('''", head)
        col = r["body_col"]
        self.assertTrue(head[:col].endswith("'''"), head[:col])
        self.assertTrue(head[col:].startswith("def f():"), head[col:])

    def test_escaped_expression_is_not_editable_in_place(self):
        # A carriage return dooms every triple-quoted form, so the exporter
        # falls back to the repr'd accumulator -- which is NOT user text laid
        # out in place and must not be offered as editable.
        n = self._node("escaped#")
        n.set_compute_expression("a = 1\r\nb = 2\n")
        _src, regions = self._gen(n)
        r = self._region(regions, "expr_compute")
        self.assertIsNotNone(r)
        self.assertFalse(r["inline"])
        self.assertFalse(r["editable"])
        self.assertIsNone(r["body_col"])

    def test_member_region_contains_its_own_def(self):
        n = self._node("member#")
        n.set_methods_source("def helper(self):\n    return 7\n")
        src, regions = self._gen(n)
        lines   = src.split("\n")
        members = [r for r in regions if r["kind"] == "method_member"]
        self.assertTrue(members)
        r = members[0]
        self.assertEqual(r["label"], "helper")
        self.assertEqual(r["owner"], "set_methods_source")
        self.assertTrue(r["editable"])
        self.assertIn("def helper", "\n".join(lines[r["start"]:r["end"] + 1]))

    def test_generated_regions_are_not_editable(self):
        n = self._node("managed#")
        _src, regions = self._gen(n)
        # No "header": the file header is the user's own text and IS editable.
        for kind in ("imports", "class_decl", "build_signature",
                     "attrs_in", "attrs_out", "return"):
            r = self._region(regions, kind)
            if r is not None:
                self.assertFalse(r["editable"], kind)
                self.assertIsNone(r["owner"], kind)

    def test_class_decl_and_return_land_exactly(self):
        n = self._node("anchors#")
        src, regions = self._gen(n)
        lines = src.split("\n")
        cd    = self._region(regions, "class_decl")
        self.assertEqual(lines[cd["start"]],
                         "class RebuiltRegions(MPyNode):")
        self.assertEqual(cd["label"], "RebuiltRegions")
        rt = self._region(regions, "return")
        self.assertEqual(lines[rt["start"]].strip(), "return node")

    def test_no_vars_region_when_none_declared(self):
        # py_export gates the block on `if var_names:`, and both reference
        # templates declare zero -- so the API view must not draw a band that
        # the bake never emits.
        n = self._node("novars#")
        _src, regions = self._gen(n)
        self.assertIsNone(self._region(regions, "vars"))

    def test_vars_region_when_declared(self):
        n = self._node("withvars#")
        n.add_variable("board", persistent=True)
        src, regions = self._gen(n)
        r = self._region(regions, "vars")
        self.assertIsNotNone(r)
        blob = "\n".join(src.split("\n")[r["start"]:r["end"] + 1])
        self.assertIn("node.add_variable('board', persistent=True)", blob)

    def test_expression_regions_carry_the_bodys_line_count_and_call_line(self):
        # What the API view prints as ``‹ N lines ›`` and the line it paints
        # it on. The count is the editor's: a trailing newline closes the last
        # line rather than opening an empty one.
        n = self._node("exprmeta#")
        n.set_init_expression("import numpy as np")
        n.set_compute_expression("pts = self.a\nself.out = pts")
        _src, regions = self._gen(n)
        init = self._region(regions, "expr_init")
        comp = self._region(regions, "expr_compute")
        self.assertEqual((init["body_lines"], init["call_offset"]), (1, 0))
        self.assertEqual((comp["body_lines"], comp["call_offset"]), (2, 0))
        self.assertEqual(init["start"], init["end"])   # one physical line
        self.assertTrue(init["inline"] and comp["inline"])
        n.set_init_expression("a = 1\nb = 2\n")
        _src, regions = self._gen(n)
        self.assertEqual(self._region(regions, "expr_init")["body_lines"], 2)

    def test_escaped_expression_names_its_call_line(self):
        # A carriage return forces the accumulator form: ``exp = ...`` lines,
        # then the call. call_offset points at the call; open_col at its paren.
        n = self._node("expresc#")
        n.set_compute_expression("a = 1\r\nb = 2\n")
        src, regions = self._gen(n)
        comp = self._region(regions, "expr_compute")
        self.assertFalse(comp["inline"])
        self.assertEqual(comp["body_lines"], 2)
        lines   = src.split("\n")
        call_no = comp["start"] + comp["call_offset"]
        self.assertEqual(call_no, comp["end"])
        call = lines[call_no]
        self.assertEqual(call.strip(), "node.set_compute_expression(exp)")
        self.assertEqual(call[comp["open_col"]:], "exp)")


class TestPersistentValuesInTheBake(unittest.TestCase):
    """``include_values`` bakes a held value as a literal or a keyed2 blob --
    never pickle -- and a None stays a declaration. Off by default, so a bake
    that did not ask is byte-identical to what it always was."""

    def _node(self, name="vals#"):
        from mpynode import MPyNode

        mc.file(new=True, force=True)
        n = MPyNode.create(name=name)
        n.add_input_attr("a", "float")
        n.add_output_attr("out", "float")
        n.set_compute_expression("self.out = self.a")
        return n

    def _gen(self, n, **kw):
        from mpynode._common.io import py_export

        return py_export.generate_node_script_with_regions(
            n, class_name="Rebuilt", **kw)

    @staticmethod
    def _vars(regions):
        return [r for r in regions if r["kind"] == "vars"][0]

    def test_default_is_declarations_only_and_unchanged(self):
        n = self._node()
        n.add_variable("board", persistent=True)
        n.set_variable("board", [1, 2, 3])
        src, regions = self._gen(n)
        self.assertIn("node.add_variable('board', persistent=True)", src)
        self.assertNotIn("set_variable(", src)
        self.assertNotIn("_stored_value", src)
        self.assertNotIn("values",        self._vars(regions))

    def test_a_literal_value_is_set_and_a_none_is_declared(self):
        n = self._node()
        n.add_variable("board", persistent=True)
        n.set_variable("board", [1, 2, 3])
        n.add_variable("empty", persistent=True)
        src, regions = self._gen(n, include_values=True)
        lines = src.split("\n")
        self.assertIn("        node.set_variable('board', [1, 2, 3], persistent=True)", lines)
        self.assertIn("        node.add_variable('empty', persistent=True)", lines)
        self.assertNotIn("_stored_value", src)         # no blob, no helper
        vars_r = self._vars(regions)
        (entry,) = vars_r["values"]
        self.assertEqual(entry["name"], "board")
        self.assertEqual(entry["summary"], "list · 3 items")
        line = lines[vars_r["start"] + entry["offset"]]
        self.assertTrue(line.startswith("        node.set_variable('board', "))
        self.assertEqual(line[entry["open_col"]:], "[1, 2, 3], persistent=True)")

    def test_an_array_goes_out_as_a_blob_with_the_helper_and_decodes(self):
        import numpy as np

        n = self._node()
        n.add_variable("weights", persistent=True)
        arr = np.arange(6, dtype="float64").reshape(3, 2)
        n.set_variable("weights", arr)
        src, regions = self._gen(n, include_values=True)
        lines  = src.split("\n")
        helper = [r for r in regions if r["kind"] == "helpers"]
        self.assertEqual(len(helper), 1)
        decl = [r for r in regions if r["kind"] == "class_decl"][0]
        self.assertLess(helper[0]["end"], decl["start"], "helper above the class")
        self.assertFalse(helper[0]["editable"])
        (entry,) = self._vars(regions)["values"]
        self.assertEqual(entry["summary"], "ndarray (3, 2) float64 · 48 B")
        value_line = lines[self._vars(regions)["start"] + entry["offset"]]
        self.assertIn("_stored_value(", value_line)
        # The helper really decodes what the line carries -- and the blob it
        # carries needs no pickle to do so.
        import ast

        from mpynode._common.io import serialization

        call = value_line.strip()[len("node.set_variable('weights', "):]
        blob = ast.literal_eval(call[len("_stored_value("):call.index(")")])
        self.assertFalse(serialization.blob_has_pickle(blob))
        ns = {}
        exec("\n".join(lines[helper[0]["start"]:helper[0]["end"] + 1]), ns)
        np.testing.assert_array_equal(ns["_stored_value"](blob), arr)

    def test_a_value_that_needs_pickle_stays_a_declaration(self):
        class Opaque:
            pass

        n = self._node()
        n.add_variable("thing", persistent=True)
        n.set_variable("thing", Opaque())
        src, regions = self._gen(n, include_values=True)
        self.assertIn("node.add_variable('thing', persistent=True)", src)
        self.assertIn("not bakeable without pickle", src)
        self.assertNotIn("set_variable('thing'", src)
        self.assertNotIn("_stored_value", src)
        self.assertNotIn("values", self._vars(regions))

    def test_numpy_scalars_are_blobs_not_literals(self):
        # ``repr(np.float64(1.5))`` reads back as a plain float; the dtype
        # would be lost, so it is not a literal.
        import numpy as np

        from mpynode._common.io import py_export

        self.assertIsNone(py_export._literal_repr(np.float64(1.5)))
        self.assertEqual(py_export._literal_repr(1.5), "1.5")
        self.assertEqual(py_export._literal_repr({"a": (1, "x")}), "{'a': (1, 'x')}")
        self.assertIsNone(py_export._literal_repr(float("nan")))
        self.assertIsNone(py_export._literal_repr("x" * 500))

    def test_summaries_read_like_a_label(self):
        import numpy as np

        from mpynode._common.io import py_export as pe

        self.assertEqual(pe.summarize_value(np.zeros((3,), "float64")),
                         "ndarray (3,) float64 · 24 B")
        self.assertEqual(pe.summarize_value(b"\x89PNG\r\n\x1a\n" + b"0" * 2040),
                         "png image · 2.0 KB")
        self.assertEqual(pe.summarize_value(b"RIFF1234WAVEfmt "), "wav audio · 16 B")
        self.assertEqual(pe.summarize_value("hello"), "str · 5 chars")
        self.assertEqual(pe.summarize_value({"a": 1, "b": 2}), "dict · 2 keys")
        self.assertEqual(pe.summarize_value(3), "int 3")
        self.assertEqual(pe.summarize_value(True), "True")
        # Audio and video containers are named, the same way the Variables tab
        # names them, so the API placeholder reads "mp4 video \u00b7 1.5 KB".
        self.assertEqual(
            pe.summarize_value(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 1524),
            "mp4 video \u00b7 1.5 KB")
        self.assertEqual(pe.summarize_value(b"ID3\x04\x00" + b"\x00" * 27),
                         "mp3 audio \u00b7 32 B")
        self.assertEqual(pe.summarize_value(b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 4),
                         "m4a audio \u00b7 16 B")

    def test_every_variable_line_is_addressable(self):
        # The Outline's variable rows locate their own line in the bake.
        n = self._node()
        n.add_variable("board", persistent=True)
        n.set_variable("board", [1, 2, 3])
        n.add_variable("empty", persistent=True)
        for include in (False, True):
            src, regions = self._gen(n, include_values=include)
            vars_r = self._vars(regions)
            lines = src.split("\n")
            self.assertEqual(set(vars_r["var_lines"]), {"board", "empty"})
            for name, offset in vars_r["var_lines"].items():
                self.assertIn("'%s'" % name, lines[vars_r["start"] + offset])


class TestTheModuleZone(unittest.TestCase):
    """The gap before ``class`` is marked as the user's insertion point when the
    Methods source has no module-scope code; the insertion line follows the
    header and the imports."""

    def _node(self, name="zone#", methods=None):
        from mpynode import MPyNode

        mc.file(new=True, force=True)
        n = MPyNode.create(name=name)
        n.add_output_attr("out", "float")
        n.set_compute_expression("self.out = 1.0")
        if methods is not None:
            n.set_methods_source(methods)
        return n

    def _regions(self, n):
        from mpynode._common.io import py_export

        return py_export.generate_node_script_with_regions(n, class_name="Z")

    def test_plain_node_marks_the_gap_before_the_class(self):
        src, regions = self._regions(self._node())
        zone = [r for r in regions if r["kind"] == "module_zone"][0]
        decl = [r for r in regions if r["kind"] == "class_decl"][0]
        self.assertTrue(zone["editable"])
        self.assertEqual(zone["owner"], "set_methods_source")
        self.assertEqual((zone["src_line"], zone["src_lines"]), (1, 0))
        self.assertEqual(zone["end"], decl["start"] - 1)
        lines = src.split("\n")
        self.assertTrue(all(not lines[i].strip()
                            for i in range(zone["start"], zone["end"] + 1)))

    def test_module_code_replaces_the_zone(self):
        _src, regions = self._regions(
            self._node("zoned#", methods="CONST = 1\n\n\ndef f(self):\n    return CONST\n"))
        kinds = [r["kind"] for r in regions]
        self.assertIn("module_segment", kinds)
        self.assertNotIn("module_zone", kinds)

    def test_a_comment_only_methods_source_bakes(self):
        # What saving a header typed into the empty top of the API view
        # produces: comments, no statement. _leading_header_block indexed
        # tree.body[0] and raised; the view then showed "The bake could not
        # be generated" right after its own save.
        src, regions = self._regions(self._node("cmt#", methods="# mine\n"))
        kinds = [r["kind"] for r in regions]
        self.assertIn("header", kinds)
        self.assertIn("module_zone", kinds)
        self.assertEqual(src.split("\n")[0], "# mine")

    def test_insert_line_follows_header_and_imports(self):
        from mpynode._common.io import py_export as pe

        self.assertEqual(pe._module_insert_line(""), 1)
        self.assertEqual(pe._module_insert_line("def f(self):\n    pass\n"), 1)
        self.assertEqual(pe._module_insert_line("import os\nimport sys\n\ndef f(self):\n    pass\n"), 3)
        self.assertEqual(pe._module_insert_line(
            "# hdr\n# more\nfrom x import (\n    y,\n)\n", header_lines=2), 6)
        self.assertEqual(pe._module_insert_line("def f(:\n"), 1)   # unparsable


class TestTheFileHeaderIsTheUsers(unittest.TestCase):
    """The top of a baked .py.

    It used to be 16 generated lines -- half of a plain node's bake -- opening
    "# Baked by the MPyNode Node Designer" and repeating the export contract on
    every node. That text is documentation, not a header, and it now lives on
    the Identity tab (``py_export.BAKE_CONTRACT``).

    What goes there instead is whatever the user wrote at the top of their
    Methods source. Both forms were broken before: a leading COMMENT block was
    dropped from the bake entirely (comments are not AST nodes, so the
    module-segment walker never saw one), and a leading DOCSTRING survived but
    was emitted BELOW the imports, where it is an ordinary string expression
    rather than the module's ``__doc__``.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _gen(self, methods_src, name="hdr#"):
        from mpynode import MPyNode
        from mpynode._common.io import py_export

        n = MPyNode.create(name=name)
        n.set_compute_expression("pass\n")
        if methods_src is not None:
            n.set_methods_source(methods_src)
        return py_export.generate_node_script_with_regions(
            n, class_name="RebuiltHeader")

    def _header(self, regions):
        for r in regions:
            if r["kind"] == "header":
                return r
        return None

    def test_no_node_bakes_the_old_preamble(self):
        src, regions = self._gen(None)
        self.assertNotIn("Baked by the MPyNode Node Designer", src)
        self.assertIsNone(self._header(regions))
        first = next(ln for ln in src.split("\n") if ln.strip())
        self.assertTrue(first.startswith("from mpynode import"), first)

    def test_a_comment_block_reaches_the_file_at_all(self):
        # This is the defect: it used to vanish without a trace.
        src, regions = self._gen("# My node.\n# Hand written.\n\n"
                                 "def helper(x):\n    return x\n")
        self.assertIn("# My node.", src)
        r = self._header(regions)
        self.assertIsNotNone(r)
        lines = src.split("\n")
        # The blank separator above the imports is INSIDE the region: it is the
        # user's line, so a space they open at the top of the file round-trips
        # instead of being re-imposed by the exporter on every bake.
        self.assertEqual(lines[r["start"]:r["end"] + 1],
                         ["# My node.", "# Hand written.", ""])

    def test_the_header_is_above_the_imports(self):
        src, regions = self._gen("# My node.\n\nimport math\n")
        lines = src.split("\n")
        r     = self._header(regions)
        imports = next(i for i, ln in enumerate(lines)
                       if ln.startswith("from mpynode import"))
        self.assertEqual(r["start"], 0)
        self.assertLess(r["end"], imports)

    def test_a_docstring_lands_where_python_reads_it(self):
        src, regions = self._gen('"""My node.\n\nSecond paragraph.\n"""\n\n'
                                 "import math\n")
        lines = src.split("\n")
        r     = self._header(regions)
        self.assertEqual(r["start"], 0)
        self.assertEqual(lines[0], '"""My node.')
        # ...and exactly once. It used to be re-emitted as a module segment
        # below the imports, so the bake carried two copies.
        self.assertEqual(src.count("Second paragraph."), 1)

    def test_the_header_splices_back_to_the_methods_source(self):
        # The API view edits this block in place, so the region has to name
        # its slice of the source it came from -- lines 1..N.
        _src, regions = self._gen("# My node.\n# Hand written.\n\n"
                                  "def helper(x):\n    return x\n")
        r = self._header(regions)
        self.assertTrue(r["editable"])
        self.assertEqual(r["owner"],     "set_methods_source")
        self.assertEqual(r["src_line"],  1)
        self.assertEqual(r["src_lines"], 3)   # two comments + the blank

    def test_a_header_free_source_keeps_its_first_function(self):
        # Nothing may be claimed as a header that the user meant as code.
        src, regions = self._gen("def helper(x):\n    return x\n")
        self.assertIsNone(self._header(regions))
        self.assertIn("def helper(x):", src)


class TestNodeInfoMetadataBanner(unittest.TestCase):
    """The Node Info metadata, baked as a generated banner above the user's own
    header.

    The compiled tier has always embedded this (a ``//`` banner + the MFnPlugin
    vendor/version); the .py bake did not, so a script that left the building
    carried no license while its compiled twin did.

    Deliberately NOT the header: the top of the file stays the user's, and the
    banner stacks above it as its own generated, read-only region -- regenerated
    from the node on every bake rather than seeded once, which is what keeps it
    from going stale the moment Node Info is edited.

    Every test here stubs ``prefs_defaults``. It reads the real Node Designer
    preferences, so a developer whose prefs carry a default license would
    otherwise see banners these tests assert are absent.
    """

    META = {"authors": ["Ada L <ada@x>"], "version": "2.1",
            "license": "(c) 2026 Studio\nMIT"}
    SRC = '"""My own header."""\n\n\ndef helper():\n    return 1\n'

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.lifecycle import metadata_registry as md

        self._md          = md
        self._saved       = md.prefs_defaults
        self._saved_flag  = md.bake_header_enabled
        md.prefs_defaults = lambda: dict(self.prefs)
        self.prefs        = {}

    def tearDown(self):
        self._md.prefs_defaults      = self._saved
        self._md.bake_header_enabled = self._saved_flag

    def _gen(self, meta, methods_src=None, name="meta#"):
        from mpynode import MPyNode
        from mpynode._common.io import py_export

        n = MPyNode.create(name=name)
        n.set_compute_expression("pass\n")
        if methods_src is not None:
            n.set_methods_source(methods_src)
        if meta is not None:
            n.set_metadata(meta)
        return py_export.generate_node_script_with_regions(n)

    def _banner(self, regions):
        for r in regions:
            if r["kind"] == "metadata":
                return r
        return None

    def test_a_node_with_metadata_bakes_a_banner(self):
        src, regions = self._gen(self.META)
        lines = src.split("\n")
        self.assertEqual(lines[0], "# " + "=" * 73)
        self.assertIn("# Generated by Node Designer.", src)
        self.assertIn("# author(s): Ada L <ada@x>", src)
        # the licence block goes in verbatim -- no label
        self.assertIn("# (c) 2026 Studio", src)
        self.assertIn("# MIT", src)
        self.assertNotIn("license:", src)
        self.assertIsNotNone(self._banner(regions))

    def test_the_build_placeholder_never_reaches_a_py(self):
        # Nothing stamps it here -- a bake does not compile -- so emitting the
        # build line would leave the literal token in the user's file.
        src, _ = self._gen(self.META)
        self.assertNotIn(self._md.BUILD_HASH_PLACEHOLDER, src)
        self.assertNotIn("build:", src)

    def test_the_banner_sits_above_the_users_own_header(self):
        src, regions = self._gen(self.META, self.SRC)
        self.assertLess(src.index("# (c) 2026 Studio"),
                        src.index('"""My own header."""'))
        # ...separated by exactly one blank line.
        lines = src.split("\n")
        at    = lines.index('"""My own header."""')
        self.assertEqual(lines[at - 1], "")
        self.assertEqual(lines[at - 2], "# " + "=" * 73)
        # Both regions exist and each still owns its own half.
        self.assertIsNotNone(self._banner(regions))
        hdr = next(r for r in regions if r["kind"] == "header")
        self.assertTrue(hdr["editable"])

    def test_the_banner_region_is_generated_not_editable(self):
        # It is regenerated from the node every time, so a keystroke here would
        # be written back nowhere and lost on the next refresh. NDApiView
        # refuses it by listing "metadata" in _GENERATED_KINDS.
        _src, regions = self._gen(self.META)
        self.assertFalse(self._banner(regions)["editable"])
        from mpynode.ui.widgets.api_view import _GENERATED_KINDS

        self.assertIn("metadata", _GENERATED_KINDS)

    def test_the_banner_owns_its_trailing_blank(self):
        """Left outside the region that blank is an unmarked line above the
        `header` block, whose default gap is 0 -- so NDApiView's spacing walker
        would report a 1-line override, and the next bake would emit the blank
        a second time. The file would grow by a line per round trip."""
        src, regions = self._gen(self.META, self.SRC)
        r     = self._banner(regions)
        lines = src.split("\n")
        self.assertEqual(lines[r["end"]], "")
        self.assertEqual(lines[r["end"] + 1], '"""My own header."""')

    def test_a_node_without_metadata_bakes_no_banner(self):
        # The empty banner is two bars and a "Generated by" -- per-node
        # boilerplate above the user's code, which is what got the old 16-line
        # preamble deleted. See py_export.BAKE_CONTRACT.
        src, regions = self._gen(None, self.SRC)
        self.assertNotIn("# ===", src)
        self.assertIsNone(self._banner(regions))
        self.assertTrue(src.lstrip().startswith('"""My own header."""'))

    def test_metadata_that_is_present_but_blank_bakes_no_banner(self):
        src, regions = self._gen({"authors": [], "version": "",
                                  "license": "", "description": "",
                                  "type_id": ""}, self.SRC)
        self.assertNotIn("# ===", src)
        self.assertIsNone(self._banner(regions))

    def test_type_id_alone_does_not_produce_a_banner_line(self):
        # type_id pins the compiled MTypeId. It is not authorship, it means
        # nothing in a .py, and it must not drag a banner into existence.
        src, regions = self._gen({"type_id": "0x0001a2b3"}, self.SRC)
        self.assertNotIn("0x0001a2b3", src)
        self.assertIsNone(self._banner(regions))

    def test_prefs_defaults_fill_a_blank_field(self):
        # The whole point of option A: the bake and the compile merge the same
        # defaults, so a node with a blank license does not compile WITH the
        # studio default and bake WITHOUT it.
        self.prefs = {"license": "(c) 2026 Studio Default"}
        src, _ = self._gen(None, self.SRC)
        self.assertIn("# (c) 2026 Studio Default", src)

    def test_a_multiline_licence_keeps_its_shape_in_the_bake(self):
        src, _ = self._gen({"license": "MIT License\n\nPermission is granted."},
                           self.SRC)
        lines = src.split("\n")
        self.assertIn("# MIT License", lines)
        self.assertIn("#", lines)                     # the blank, bare prefix
        self.assertIn("# Permission is granted.", lines)
        self.assertNotIn("license:", src)
        # Still a valid Python file: nothing escaped its comment.
        compile(src, "<bake>", "exec")

    def test_the_preference_suppresses_the_whole_banner(self):
        self._md.bake_header_enabled = lambda default=True: False
        try:
            src, regions = self._gen(self.META, self.SRC)
            self.assertNotIn("# ===", src)
            self.assertIsNone(self._banner(regions))
        finally:
            self._md.bake_header_enabled = self._saved_flag

    def test_the_preference_beats_a_studio_default_too(self):
        # With the merge left outside the gate, a global default license
        # would keep producing a banner and the switch would look broken.
        self.prefs                   = {"license": "(c) Studio Default"}
        self._md.bake_header_enabled = lambda default=True: False
        try:
            src, _ = self._gen(None, self.SRC)
            self.assertNotIn("Studio Default", src)
            self.assertNotIn("# ===", src)
        finally:
            self._md.bake_header_enabled = self._saved_flag

    def test_the_node_wins_over_the_prefs_default(self):
        self.prefs = {"license": "(c) Global", "description": "global desc"}
        src, _ = self._gen({"license": "(c) Mine"}, self.SRC)
        self.assertIn("# (c) Mine", src)
        self.assertNotIn("(c) Global", src)
        # an untouched field still inherits its studio default
        self.assertIn("# description: global desc", src)


if __name__ == "__main__":
    unittest.main()
