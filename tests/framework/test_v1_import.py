"""Importing a v1 (``node-designer``) node out of a ``.ma``.

Every fixture here is synthetic and small. The real corpus -- the nine scenes
in the upstream ``examples/`` folder -- is 10 MB and lives in another
repository, so the cases it exposed are reproduced as minimal `.ma` fragments
instead. Each of the parsing tests below corresponds to something a real file
actually did and an earlier draft of the importer got wrong.
"""

from __future__ import annotations

import base64
import io
import os
import pickle
import tempfile
import unittest

from mpynode._common.io import v1_import as V


def _b64(obj, protocol=pickle.HIGHEST_PROTOCOL):
    """base64 with the line breaks removed -- a MEL string literal cannot
    carry a raw newline, and the importer strips whitespace anyway."""
    raw = base64.encodebytes(pickle.dumps(obj, protocol=protocol)).decode()
    return "".join(raw.split())


def _ma(expression="", inputs=None, outputs=None, stored=None, wrap=False,
        name="v1node"):
    """A minimal .ma carrying one v1 mPyNode."""
    L = ['//Maya ASCII 2024 scene', 'requires maya "2024";',
         'createNode transform -name "someOtherNode";',
         'createNode mPyNode -name "%s";' % name,
         '\trename -uuid "AAAA-BBBB";']

    def setattr_str(plug, payload):
        if wrap:
            L.append('\tsetAttr ".%s" -type "string" (' % plug)
            chunk = 40
            bits = [payload[i:i + chunk] for i in range(0, len(payload), chunk)]
            for k, bit in enumerate(bits):
                L.append('\t\t%s"%s"' % ("" if k == 0 else "+ ", bit))
        else:
            L.append('\tsetAttr ".%s" -type "string" "%s";' % (plug, payload))

    if expression:
        setattr_str("expression", expression.replace("\n", chr(92) + "n"))
    if inputs is not None:
        setattr_str("_inputAttrs", _b64({k: [v] for k, v in inputs.items()}).strip())
    if outputs is not None:
        setattr_str("_outputAttrs", _b64({k: [v] for k, v in outputs.items()}).strip())
    if stored is not None:
        setattr_str("_storedVarsData", _b64(stored).strip())
    L.append('createNode lambert -name "trailing";')
    return "\n".join(L) + "\n"


def _write(text):
    fd, path = tempfile.mkstemp(suffix=".ma")
    os.close(fd)
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class TestReadingTheFile(unittest.TestCase):

    def _read(self, **kw):
        path = _write(_ma(**kw))
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return V.read_v1_ma(path)

    def test_only_mpynodes_are_picked_up(self):
        nodes = self._read(expression="x = 1", inputs={"a": "float"})
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].name, "v1node")

    def test_attrs_and_stored_vars_decode(self):
        n = self._read(expression="out = a",
                       inputs={"a": "float", "m": "matrix"},
                       outputs={"out": "vector"},
                       stored={"count": 7})[0]
        self.assertEqual(n.inputs, {"a": "float", "m": "matrix"})
        self.assertEqual(n.outputs, {"out": "vector"})
        self.assertEqual(n.stored_vars, {"count": 7})

    def test_the_payload_is_the_LAST_string_on_the_line(self):
        # `setAttr "._inputAttrs" -type "string" "<b64>"` has three quoted
        # runs. Taking the first yielded the plug name plus everything after
        # it, and every real file failed to decode.
        n = self._read(expression="out = a", inputs={"a": "float"},
                       outputs={"out": "float"})[0]
        self.assertEqual(n.inputs, {"a": "float"})

    def test_a_wrapped_multi_line_payload(self):
        # Maya splits any long string across `( "..." + "..." )`. Real files do
        # this for both the expression AND the pickle plugs once they are big
        # enough -- four of the nine upstream examples.
        n = self._read(expression="out = a\nout = out + 1",
                       inputs={"a": "float"}, outputs={"out": "float"},
                       stored={"k": list(range(40))}, wrap=True)[0]
        self.assertEqual(n.inputs, {"a": "float"})
        self.assertEqual(n.stored_vars["k"], list(range(40)))
        self.assertIn("out = a", n.expression)

    def test_a_continuation_run_ends_without_a_closing_paren_line(self):
        # Maya writes the final fragment and the ");" together, so the next
        # setAttr follows immediately. A parser waiting for a lone ")" ate the
        # rest of the node.
        n = self._read(expression="out = a", inputs={"a": "float"},
                       outputs={"out": "float"}, stored={"z": 1}, wrap=True)[0]
        self.assertEqual(n.stored_vars, {"z": 1})

    def test_mixed_pickle_protocols_in_one_node(self):
        # quaternionSpineNode.ma really is like this: written across the
        # Python 2 -> 3 migration, protocol 2 on one plug and 4 on another.
        path = _write(_ma(expression="out = a", inputs={"a": "float"},
                          outputs={"out": "float"})
                      .replace(_b64({"a": ["float"]}).strip(),
                               _b64({"a": ["float"]}, protocol=2).strip()))
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        self.assertEqual(V.read_v1_ma(path)[0].inputs, {"a": "float"})

    def test_silently_empty_attrs_are_an_error(self):
        # v1's _loadPickle ends in a bare `except: pass`, so corrupt data reads
        # as empty. An expression with no attributes is far likelier to be that
        # than a genuinely attribute-less node.
        path = _write(_ma(expression="out = 1"))
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with self.assertRaises(V.V1ImportError):
            V.read_v1_ma(path)


class TestTheUnpickler(unittest.TestCase):
    """v1 stored vars can hold v1's OWN classes -- unitSphereCollisionNode.ma
    stores a list of ``mpylib._mpynode._openmaya.MPoint``. Requiring v1 on
    sys.path to read them would defeat the whole file-based approach."""

    def test_a_v1_class_demotes_to_plain_numbers(self):
        payload = (b'cmpylib._mpynode._openmaya' + bytes([10])
                   + b'MPoint' + bytes([10])
                   + b'(F1.0' + bytes([10]) + b'F2.0' + bytes([10])
                   + b'F3.0' + bytes([10]) + b'tR.')
        got = V._unpickle_b64(base64.encodebytes(payload).decode())
        self.assertEqual(got, [1.0, 2.0, 3.0])

    def test_an_unexpected_module_is_refused(self):
        # Untrusted input: allowing an explicit set beats letting pickle import
        # whatever it is told to.
        payload = (b'cos' + bytes([10]) + b'system' + bytes([10])
                   + b"(S'echo hi'" + bytes([10]) + b'tR.')
        with self.assertRaises(V.V1ImportError):
            V._unpickle_b64(base64.encodebytes(payload).decode())


class TestExpressionConversion(unittest.TestCase):

    def test_reads_and_writes_become_self(self):
        init, comp, rep = V.split_and_selfify(
            "out = a * 2", {"a": "float"}, {"out": "float"})
        self.assertIn("self.out", comp)
        self.assertIn("self.a", comp)
        self.assertEqual(rep["rewrites"], 2)

    def test_imports_and_defs_go_to_init(self):
        init, comp, rep = V.split_and_selfify(
            "import math\n\ndef helper(x):\n    return x + 1\n\nout = helper(a)",
            {"a": "float"}, {"out": "float"})
        self.assertIn("import math", init)
        self.assertIn("def helper", init)
        self.assertNotIn("def helper", comp)
        self.assertIn("self.out", comp)

    def test_a_shadowed_input_gets_an_alias_not_a_rewrite(self):
        # v1 semantics: assigning to an input made a plain local and did NOT
        # write the plug -- but the name still STARTED as the plug value, and
        # splineNode reads `degree` before assigning to it. Leaving it bare
        # alone raised NameError.
        init, comp, rep = V.split_and_selfify(
            "d = degree + 1\ndegree = 3\nout = degree",
            {"degree": "int"}, {"out": "int"})
        self.assertEqual(rep["shadowed"], ["degree"])
        self.assertEqual(comp.splitlines()[0], "degree = self.degree")
        self.assertNotIn("self.degree + 1", comp)

    def test_an_output_is_rewritten_even_though_it_is_assigned(self):
        # Assigning an output IS the plug write; that is the point.
        _i, comp, _r = V.split_and_selfify("out = 1", {}, {"out": "float"})
        self.assertIn("self.out = 1", comp)

    def test_strings_and_comments_are_untouched(self):
        # The reason this is an AST pass and not a regex.
        src = "# a is nice\nmsg = 'a'\nout = a"
        _i, comp, _r = V.split_and_selfify(src, {"a": "float"}, {"out": "float"})
        self.assertIn("'a'", comp)
        self.assertIn("self.a", comp)
        self.assertNotIn("self.a'", comp)

    def test_a_helper_reading_a_plug_as_a_global_is_reported(self):
        # v1 helpers saw plug values because they were module-level locals. In
        # v2 helpers live in Init and cannot see self, so these need finishing.
        _i, _c, rep = V.split_and_selfify(
            "def f():\n    return a\n\nout = f()",
            {"a": "float"}, {"out": "float"})
        self.assertEqual(rep["globals_in_defs"], ["a"])

    def test_a_syntax_error_is_reported_not_swallowed(self):
        with self.assertRaises(V.V1ImportError):
            V.split_and_selfify("def (:", {}, {})


class TestEnumSynthesis(unittest.TestCase):
    """v1 stored `['enum']` and no labels at all, and v2 rejects an enum with
    no enum_names -- so the importer has to invent them."""

    def test_the_count_comes_from_what_it_is_compared_against(self):
        names = V.synth_enum_names("mode", "if mode == 2:\n    pass")
        self.assertEqual(names, ["0", "1", "2"])

    def test_a_minimum_of_two(self):
        self.assertEqual(V.synth_enum_names("mode", "x = 1"), ["0", "1"])

    def test_unparseable_source_still_yields_something_usable(self):
        self.assertEqual(V.synth_enum_names("mode", "def (:"), ["0", "1"])


class TestHandFinishReporting(unittest.TestCase):
    """v1 handed plug values as its own MPoint/MVector/MMatrix shims and made
    those names ambient; v2 hands numpy and MatrixView. Arithmetic written
    against the old model does not type-check, and no converter can guess its
    way through that -- so it is reported."""

    def _spec(self, expr, ins, outs):
        n = V.V1Node("n")
        n.expression, n.inputs, n.outputs = expr, ins, outs
        return V.convert(n)

    def test_api_object_use_is_flagged(self):
        spec = self._spec("out = MVector(0, 0, 0)", {}, {"out": "vector"})
        self.assertEqual(spec["api_objects"], ["MVector"])
        self.assertTrue(spec["needs_hand_finish"])

    def test_plain_numeric_code_is_not_flagged(self):
        spec = self._spec("out = a * 2", {"a": "float"}, {"out": "float"})
        self.assertEqual(spec["api_objects"], [])
        self.assertFalse(spec["needs_hand_finish"])

    def test_the_report_carries_what_the_user_must_act_on(self):
        spec = self._spec("out = MPoint(a, 0, 0)", {"a": "float"},
                          {"out": "vector"})
        for key in ("shadowed", "globals_in_defs", "synthesized_enums",
                    "api_objects", "needs_hand_finish", "init", "compute"):
            self.assertIn(key, spec, key)


class TestApiTypeFixes(unittest.TestCase):
    """The two v1->v2 type mismatches the converter repairs outright.

    Both were found by evaluating a real converted node rather than by reading
    v1's source, and they hide behind each other: on
    ``quaternionSpineNode.ma`` fixing the first only reveals the second, and
    the node runs clean once both are done. Four edit sites in 52 lines --
    which is why they are worth automating rather than reporting.

    Both rules key off the DECLARED attribute type, never off inferring what
    an expression evaluates to, so neither can fire on something that merely
    looks like a plug read.
    """

    def _conv(self, src, ins, outs):
        return V.split_and_selfify(src, ins, outs)

    # -- class 1: a matrix plug read is a MatrixView, not an MMatrix --------

    def test_a_qualified_matrix_ctor_on_a_plug_is_rewritten(self):
        _i, comp, rep = self._conv("out = om.MTransformationMatrix(m)",
                                   {"m": "matrix"}, {"out": "matrix"})
        self.assertIn("self.m.asTransformationMatrix()", comp)
        self.assertNotIn("MTransformationMatrix(", comp)
        self.assertEqual(len(rep["matrix_view_fixes"]), 1)

    def test_the_bare_ctor_form_is_rewritten_too(self):
        # v1 made MMatrix/MPoint/MVector ambient in the expression namespace,
        # and real v1 nodes use both the bare and the om.-qualified form.
        _i, comp, _r = self._conv("out = MMatrix(m)",
                                  {"m": "matrix"}, {"out": "matrix"})
        self.assertIn("self.m.asMatrix()", comp)

    def test_an_array_element_is_rewritten(self):
        # An element of a matrix ARRAY plug is a MatrixView just as a single
        # matrix plug is -- this is the form the spine example actually used.
        _i, comp, _r = self._conv(
            "out = om.MTransformationMatrix(m[i])",
            {"m": "matrix"}, {"out": "matrix"})
        self.assertIn("self.m[i].asTransformationMatrix()", comp)

    def test_a_non_plug_argument_is_left_alone(self):
        # A helper returning a real MMatrix must keep its constructor.
        _i, comp, rep = self._conv(
            "out = om.MTransformationMatrix(buildMatrix(1))",
            {}, {"out": "matrix"})
        self.assertIn("om.MTransformationMatrix(buildMatrix(1))", comp)
        self.assertEqual(rep["matrix_view_fixes"], [])

    def test_a_plug_of_the_wrong_type_is_left_alone(self):
        _i, comp, rep = self._conv("out = om.MMatrix(f)",
                                   {"f": "float"}, {"out": "matrix"})
        self.assertIn("om.MMatrix(self.f)", comp)
        self.assertEqual(rep["matrix_view_fixes"], [])

    def test_a_multi_argument_ctor_is_left_alone(self):
        _i, comp, _r = self._conv("out = om.MMatrix(m, m)",
                                  {"m": "matrix"}, {"out": "matrix"})
        self.assertIn("om.MMatrix(self.m, self.m)", comp)

    # -- class 2: an MPoint has four components, a vector plug has three ----

    def test_a_computed_write_to_a_vector_plug_is_wrapped(self):
        _i, comp, rep = self._conv("out = curve.getPointAtParam(0)",
                                   {}, {"out": "vector"})
        self.assertIn("_v1_vec3(curve.getPointAtParam(0))", comp)
        self.assertEqual(rep["vec3_fixes"], ["out"])

    def test_arithmetic_is_wrapped_even_with_no_api_call_on_the_line(self):
        # The spine wrote `p0 + t0 * n`, MPoint-valued with nothing on the
        # line to infer that from. This is why the fix is a shim rather than
        # a table of api return types.
        _i, comp, _r = self._conv("out = p0 + t0 * 3",
                                  {}, {"out": "vector"})
        self.assertIn("_v1_vec3(p0 + t0 * 3)", comp)

    def test_a_three_element_display_is_not_wrapped(self):
        # Already the right shape, and by far the common case -- wrapping it
        # would be pure noise.
        _i, comp, rep = self._conv("out = [1, 2, 3]", {}, {"out": "vector"})
        self.assertIn("out = [1, 2, 3]", comp)
        self.assertNotIn("_v1_vec3", comp)
        self.assertEqual(rep["vec3_fixes"], [])

    def test_euler_and_colour_plugs_are_covered(self):
        _i, comp, rep = self._conv("a = f()\nb = g()",
                                   {}, {"a": "euler", "b": "color"})
        self.assertIn("_v1_vec3(f())", comp)
        self.assertIn("_v1_vec3(g())", comp)
        self.assertEqual(rep["vec3_fixes"], ["a", "b"])

    def test_a_non_vector_plug_is_not_wrapped(self):
        _i, comp, rep = self._conv("out = f()", {}, {"out": "float"})
        self.assertNotIn("_v1_vec3", comp)
        self.assertEqual(rep["vec3_fixes"], [])

    def test_an_array_element_write_is_wrapped(self):
        _i, comp, _r = self._conv("out[i] = f()", {}, {"out": "vector"})
        self.assertIn("_v1_vec3(f())", comp)

    # -- the shim ----------------------------------------------------------

    def test_the_shim_lands_in_init_when_needed(self):
        init, _c, _r = self._conv("out = f()", {}, {"out": "vector"})
        self.assertIn("def _v1_vec3(v):", init)

    def test_no_shim_when_nothing_needs_it(self):
        # A node that does not need it gets no mystery function to wonder at.
        init, _c, _r = self._conv("out = [1, 2, 3]", {}, {"out": "vector"})
        self.assertNotIn("_v1_vec3", init)

    def test_the_shim_truncates_four_and_passes_three_through(self):
        init, _c, _r = self._conv("out = f()", {}, {"out": "vector"})
        ns = {}
        exec(compile(init, "<init>", "exec"), ns)
        shim = ns["_v1_vec3"]
        self.assertEqual(shim([1, 2, 3, 1]), [1, 2, 3])
        self.assertEqual(shim([1, 2, 3]), [1, 2, 3])
        self.assertEqual(shim(7.5), 7.5)          # not a sequence at all

    def test_the_pass_is_idempotent(self):
        # convert() may be re-run on the same source; a double wrap would
        # still be correct but would look like a bug.
        _i, comp, _r = self._conv("out = f()", {}, {"out": "vector"})
        _i2, comp2, _r2 = self._conv(comp.replace("self.", ""), {},
                                     {"out": "vector"})
        self.assertEqual(comp2.count("_v1_vec3"), 1)


class TestDeadV1LibraryImports(unittest.TestCase):
    """``from mpylib import MVector`` cannot be satisfied under v2, and must be
    dropped rather than left to fail.

    Four of the nine upstream examples do this. Leaving the import in place is
    far worse than removing it, because Init is ALL-OR-NOTHING: the
    ModuleNotFoundError aborts the whole exec, so every other Init name --
    unrelated imports, helper defs, the ``_v1_vec3`` shim -- disappears with
    it, and Compute then reports whichever of those it reaches first. On
    gameOfLifeNode that surfaced as ``NameError: name '_v1_vec3' is not
    defined``: a trail pointing at the importer's own shim rather than at the
    dead import. After the drop the same scene reports
    ``NameError: name 'MVector' is not defined``, which is the truth.
    """

    def test_the_import_is_dropped_and_reported(self):
        init, _c, rep = V.split_and_selfify(
            "from mpylib import MVector\nout = MVector(1, 2, 3)[0]",
            {}, {"out": "float"})
        self.assertNotIn("mpylib", init)
        self.assertEqual(rep["dead_imports"], ["from mpylib import MVector"])

    def test_a_plain_import_is_dropped(self):
        init, _c, rep = V.split_and_selfify(
            "import mpylib\nout = 1.0", {}, {"out": "float"})
        self.assertNotIn("mpylib", init)
        self.assertEqual(rep["dead_imports"], ["import mpylib"])

    def test_a_submodule_import_is_dropped(self):
        _i, _c, rep = V.split_and_selfify(
            "from mpylib.api import openmaya\nout = 1.0",
            {}, {"out": "float"})
        self.assertEqual(rep["dead_imports"],
                         ["from mpylib.api import openmaya"])

    def test_an_unrelated_import_on_the_same_line_survives(self):
        # Collateral damage would be worse than the original problem.
        init, _c, rep = V.split_and_selfify(
            "import mpylib, math\nout = math.pi", {}, {"out": "float"})
        self.assertIn("import math", init)
        self.assertNotIn("mpylib", init)
        self.assertEqual(rep["dead_imports"], ["import mpylib"])

    def test_other_imports_are_untouched(self):
        init, _c, rep = V.split_and_selfify(
            "import random\nfrom bisect import bisect_left as bl\nout = 1.0",
            {}, {"out": "float"})
        self.assertIn("import random", init)
        self.assertIn("bisect_left as bl", init)
        self.assertEqual(rep["dead_imports"], [])

    def test_the_rest_of_init_still_executes(self):
        # The whole point. Before the drop this Init raised
        # ModuleNotFoundError and neither `helper` nor the shim existed.
        init, _c, _r = V.split_and_selfify(
            "from mpylib import MVector\nimport math\n"
            "def helper(x):\n    return x * 2\n\nout = helper(1)",
            {}, {"out": "vector"})
        ns = {}
        exec(compile(init, "<init>", "exec"), ns)
        self.assertEqual(ns["helper"](3), 6)
        self.assertIn("math", ns)
        self.assertIn("_v1_vec3", ns)

    def test_a_nested_import_is_reported_but_left_alone(self):
        # It fails when the function is CALLED, not during Init, so it does
        # not poison the namespace -- and removing it could leave an empty
        # function body. Reporting is enough.
        init, _c, rep = V.split_and_selfify(
            "def f():\n    from mpylib import MVector\n    return MVector()\n"
            "\nout = 1.0", {}, {"out": "float"})
        self.assertIn("from mpylib import MVector", init)
        self.assertEqual(rep["dead_imports"], ["mpylib"])
